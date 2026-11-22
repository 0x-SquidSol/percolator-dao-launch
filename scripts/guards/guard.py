#!/usr/bin/env python3
"""Repository leak guards.

This repository is public. These checks refuse changes that could leak
private material. Generic rules live in this file. Project-specific patterns
are loaded from a git-ignored local file (private/guard-patterns.txt) or, in
CI, from the GUARD_PATTERNS secret, so they are never stored in the repo.

Output never prints the matched text, so hook output and CI logs stay clean.

Usage:
  guard.py staged            check staged changes (pre-commit hook)
  guard.py message <file>    check a commit message and branch (commit-msg hook)
  guard.py pre-push          check refs and commits about to be pushed (pre-push hook)
  guard.py tree              check every tracked file (CI)
  guard.py commits <range>   check every commit in a range: identities,
                             messages, file names and file contents (CI)
  guard.py ref <name>        check a branch or tag name (CI)
"""
import os
import re
import subprocess
import sys

# Make the sibling module importable however the script is started.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gitfiles  # noqa: E402
import textscan  # noqa: E402

PATTERNS_FILE = os.path.join("private", "guard-patterns.txt")

ALLOWED_EMAIL = re.compile(
    r"(@percolator\.trade|@users\.noreply\.github\.com|^noreply@github\.com)$",
    re.IGNORECASE,
)

FORBIDDEN_PATHS = [
    (re.compile(r"private", re.IGNORECASE), "path contains 'private'"),
    (re.compile(r"(^|/)\.env(\.(?!example$)[^/]*)?$"), "environment file"),
    (re.compile(r"keypair[^/]*\.json$", re.IGNORECASE), "keypair file"),
    (re.compile(r"(^|/)id\.json$"), "wallet file"),
    (re.compile(r"\.pem$", re.IGNORECASE), "private key file"),
]

# A Solana secret key exported as JSON: an array of exactly 64 byte values.
SECRET_KEY_ARRAY = re.compile(r"\[\s*(?:\d{1,3}\s*,\s*){63}\d{1,3}\s*\]")


def git(*args, check=True):
    result = subprocess.run(["git", *args], capture_output=True)
    if check and result.returncode != 0:
        # Name only the git subcommand: its arguments may contain file names.
        sys.exit(f"guard: refusing, 'git {args[0]}' failed (fetch or check the repository)")
    return result.stdout


def fail(problems):
    print("guard: refusing, possible leak of private material:", file=sys.stderr)
    for problem in problems:
        print("  - " + problem, file=sys.stderr)
    sys.exit(1)


def load_patterns():
    raw = os.environ.get("GUARD_PATTERNS")
    if raw is None and os.path.isfile(PATTERNS_FILE):
        with open(PATTERNS_FILE, encoding="utf-8") as handle:
            raw = handle.read()
    patterns = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(re.compile(line, re.IGNORECASE))
    if not patterns:
        fail([
            "no private guard patterns found: add private/guard-patterns.txt "
            "(see scripts/README.md) or set GUARD_PATTERNS"
        ])
    return patterns


def check_name(label, name, patterns, problems):
    for index, pattern in enumerate(patterns, 1):
        if pattern.search(name):
            problems.append(f"{label} matches private pattern #{index}")


def shown(path, patterns):
    """The path as it may be printed: hidden if it matches a private pattern."""
    if any(pattern.search(path) for pattern in patterns):
        return "<path hidden>"
    return path


def check_path(path, patterns, problems):
    label = shown(path, patterns)
    for pattern, why in FORBIDDEN_PATHS:
        if pattern.search(path):
            problems.append(f"{label}: {why}")
    check_name(f"{label}: file name", path, patterns, problems)


def check_text(label, data, patterns, problems):
    """Checks every readable view of the data (see textscan.py), so text in
    UTF-16, UTF-32, other encodings or inside binary files is checked too.
    A pattern matches if it matches any single line, the same rule as for
    plain text. Reports never include the matched text."""
    if len(data) > textscan.MAX_SCAN_BYTES:
        problems.append(f"{label}: too large to inspect (over 25 MB)")
        return
    key_found = False
    reported = set()  # patterns already reported for this file
    for view, text in textscan.text_views(data):
        if not key_found and SECRET_KEY_ARRAY.search(text):
            key_found = True
            problems.append(f"{label}: looks like a secret key (64-number array)")
        for number, line in enumerate(text.splitlines(), 1):
            for index, pattern in enumerate(patterns, 1):
                if view and index in reported:
                    continue
                if pattern.search(line):
                    reported.add(index)
                    if view:
                        problems.append(f"{label}: matches private pattern #{index} (read as {view})")
                    else:
                        problems.append(f"{label}:{number}: matches private pattern #{index}")


def check_email(label, email, problems):
    if not ALLOWED_EMAIL.search(email.strip()):
        problems.append(f"{label} email is not a project or GitHub noreply address")


def ident_email(variable):
    match = re.search(r"<([^>]*)>", git("var", variable).decode(errors="replace"))
    return match.group(1) if match else ""


def check_entries(prefix, listing, patterns, problems, blobs):
    """Checks the names and stored content of entries from gitfiles, and
    reports every refusal (submodules, unmerged or unknown entries)."""
    entries, refusals = listing
    for refusal in refusals:
        check_path(refusal.path, patterns, problems)
        problems.append(f"{prefix}{shown(refusal.path, patterns)}: refused, {refusal.reason}")
    for entry in entries:
        check_path(entry.path, patterns, problems)
        label = f"{prefix}{shown(entry.path, patterns)}"
        data = blobs.read(entry.sha)
        if data is None:
            problems.append(f"{label}: too large to inspect (over 25 MB)")
        else:
            check_text(label, data, patterns, problems)


def mode_staged(patterns):
    problems = []
    with gitfiles.Blobs() as blobs:
        check_entries("", gitfiles.staged(), patterns, problems, blobs)
    check_email("author", ident_email("GIT_AUTHOR_IDENT"), problems)
    check_email("committer", ident_email("GIT_COMMITTER_IDENT"), problems)
    return problems


def mode_message(patterns, message_file):
    problems = []
    with open(message_file, "rb") as handle:
        raw = handle.read()
    # The whole message, comment lines included (git keeps "#" lines in some
    # cleanup modes), as raw bytes so every encoding view applies.
    check_text("commit message", raw, patterns, problems)
    branch = git("symbolic-ref", "--short", "-q", "HEAD", check=False).decode().strip()
    if branch:
        check_name("branch name", branch, patterns, problems)
    return problems


def mode_tree(patterns):
    """Every file in the index, as stored (not the working tree)."""
    problems = []
    with gitfiles.Blobs() as blobs:
        check_entries("", gitfiles.in_index(), patterns, problems, blobs)
    return problems


def commit_bodies(shas):
    """Each commit's message as raw bytes, read in one `git cat-file --batch`
    call. Refuses (exits) on anything unexpected rather than skipping."""
    if not shas:
        return {}
    result = subprocess.run(
        ["git", "cat-file", "--batch"],
        input=("\n".join(shas) + "\n").encode(), capture_output=True,
    )
    if result.returncode != 0:
        sys.exit("guard: refusing, 'git cat-file' failed (fetch or check the repository)")
    out, pos, bodies = result.stdout, 0, {}
    for sha in shas:
        end = out.find(b"\n", pos)
        header = out[pos:end].split() if end >= 0 else []
        if len(header) != 3 or header[0].decode() != sha or header[1] != b"commit":
            sys.exit("guard: refusing, could not read a commit object")
        size = int(header[2])
        raw = out[end + 1:end + 1 + size]
        pos = end + 1 + size + 1  # content, then a newline
        bodies[sha] = raw.split(b"\n\n", 1)[1] if b"\n\n" in raw else b""
    return bodies


def mode_commits(patterns, revision_range):
    """Check every commit, not just the final files: a leak added and then
    removed in the same push would otherwise stay public in history."""
    problems = []
    log = git("log", "--format=%H%x00%ae%x00%ce", revision_range).decode("utf-8", errors="replace")
    commits = [line.split("\0") for line in log.splitlines() if line]
    bodies = commit_bodies([sha for sha, _, _ in commits])
    with gitfiles.Blobs() as blobs:
        for sha, author, committer in commits:
            short = sha[:10]
            check_email(f"commit {short} author", author, problems)
            check_email(f"commit {short} committer", committer, problems)
            # The message exactly as stored, so every encoding view applies.
            check_text(f"commit {short} message", bodies[sha], patterns, problems)
            # Files each commit adds or changes against every parent (so
            # content introduced while resolving a merge is checked too).
            check_entries(f"commit {short} ", gitfiles.in_commit(sha), patterns, problems, blobs)
    return problems


ZERO_SHA = re.compile(r"^0+$")


def ref_short_name(ref):
    return re.sub(r"^refs/(heads|tags)/", "", ref)


def mode_pre_push(patterns):
    """Runs before anything leaves this computer. Git passes one line per ref:
    <local ref> <local sha> <remote ref> <remote sha>."""
    problems = []
    for line in sys.stdin.read().splitlines():
        parts = line.split()
        if len(parts) != 4 or ZERO_SHA.match(parts[1]):
            continue  # malformed line, or deleting a remote ref
        _, local_sha, remote_ref, remote_sha = parts
        check_name("pushed ref name", ref_short_name(remote_ref), patterns, problems)
        if ZERO_SHA.match(remote_sha):
            revision_range = local_sha  # new remote ref: check all of its history
        else:
            revision_range = f"{remote_sha}..{local_sha}"
        problems += mode_commits(patterns, revision_range)
    return problems


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    if mode == "message" and len(argv) == 3:
        argv = [argv[0], mode, os.path.abspath(argv[2])]
    os.chdir(git("rev-parse", "--show-toplevel").decode().strip())
    if mode == "staged" and len(argv) == 2:
        problems = mode_staged(load_patterns())
    elif mode == "message" and len(argv) == 3:
        problems = mode_message(load_patterns(), argv[2])
    elif mode == "tree" and len(argv) == 2:
        problems = mode_tree(load_patterns())
    elif mode == "commits" and len(argv) == 3:
        problems = mode_commits(load_patterns(), argv[2])
    elif mode == "pre-push" and len(argv) == 2:
        problems = mode_pre_push(load_patterns())
    elif mode == "ref" and len(argv) == 3:
        problems = []
        check_name("ref name", ref_short_name(argv[2]), load_patterns(), problems)
    else:
        sys.exit(__doc__)
    if problems:
        fail(problems)


if __name__ == "__main__":
    main(sys.argv)
