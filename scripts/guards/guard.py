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
# --- start-up block: the same in every script run directly (a test checks) ---
# Python searches this script's folder first, and there a committed package
# folder, compiled extension or cached bytecode wins over the reviewed .py
# file, and a file such as subprocess.py replaces the real module. So before
# anything else is imported, every folder inside the repository leaves the
# import path, and sibling modules are compiled from their source text only.
import sys  # built in

if "os" not in sys.modules:  # loaded by start-up, before this folder is searched
    sys.exit("guard: refusing, Python started without its usual set-up (-S?)")
import os  # noqa: E402

HERE = os.path.dirname(os.path.realpath(__file__))


def _in_repository(folder):
    top = os.path.normcase(os.path.dirname(os.path.dirname(HERE)))
    place = os.path.normcase(os.path.realpath(folder or os.curdir))
    return place == top or place.startswith(top.rstrip(os.sep) + os.sep)


if __name__ == "__main__":
    sys.path[:] = [folder for folder in sys.path if not _in_repository(folder)]


def load_sibling(name):
    """NAME.py beside this script, compiled from its source: never cached
    bytecode, a compiled extension or a package folder of that name."""
    if name not in sys.modules:
        path = os.path.join(HERE, name + ".py")
        module = sys.modules[name] = type(sys)(name)
        module.__file__ = path
        with open(path, "rb") as handle:
            exec(compile(handle.read(), path, "exec", dont_inherit=True), module.__dict__)
    return sys.modules[name]
# --- end of start-up block ---

import codecs  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402

textscan = load_sibling("textscan")  # before gitfiles, which imports it
gitfiles = load_sibling("gitfiles")

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
    # Python could run these in place of reviewed source (see the start-up
    # block above), so they are refused even though it no longer does.
    (re.compile(r"(^|/)__pycache__/|\.py[cdo]$|^scripts/.*\.so$", re.IGNORECASE),
     "compiled Python file"),
    (re.compile(r"^(?i:scripts/guards)/(?![a-z0-9_]+\.py$|setup\.sh$)"),
     "only .py source files and setup.sh belong in scripts/guards"),
]

# A Solana secret key exported as JSON: an array of exactly 64 byte values.
SECRET_KEY_ARRAY = re.compile(r"\[\s*(?:\d{1,3}\s*,\s*){63}\d{1,3}\s*\]")


def git(*args, check=True):
    result = subprocess.run([gitfiles.git_exe(), *args], capture_output=True)
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


def check_ident(label, name, email, patterns, problems):
    """One author or committer, as stored bytes: name and email are free
    text, so both get every check_text view, and the email must also be an
    allowed address. Labels never show either."""
    check_text(f"{label} name", name, patterns, problems)
    check_text(f"{label} email", email, patterns, problems)
    check_email(label, email.decode("utf-8", errors="replace"), problems)


def check_declared(label, data, encoding, patterns, problems):
    """data also read in the text encoding a commit declares (or git is set
    to declare), which the usual views may not cover. An unknown encoding,
    or a codec that isn't text (rot13, base64, hex), is refused."""
    try:
        if not getattr(codecs.lookup(encoding), "_is_text_encoding", True):
            raise LookupError(encoding)
        declared = data.decode(encoding, errors="replace")
    except (LookupError, UnicodeError, ValueError):
        problems.append(f"{label}: unknown text encoding, refused")
        return
    check_text(f"{label} (declared encoding)", declared.encode("utf-8"), patterns, problems)


def check_signature(label, payload, armored, patterns, problems):
    """A signature, checked like any text. Its data is random, so a short
    pattern can match it by chance; that is excused only when it is a
    genuine signature of payload by a pinned key (gitfiles.SIGNING_KEYS).
    payload is None where no excuse applies."""
    found = []
    check_text(label, armored, patterns, found)
    if found and not (payload is not None and gitfiles.genuine_signature(payload, armored)):
        problems.extend(found)


def check_tag(label, tag, patterns, problems):
    """One annotated tag object, pushed or embedded in a merge commit: the
    object as text, its signature (split off as git does, see
    check_signature) and every tagger email. Labels never use the tag's
    name, which could match a pattern."""
    payload, signature = gitfiles.split_signed_tag(tag.raw)
    check_text(label, payload, patterns, problems)
    if signature:
        check_signature(f"{label} signature", payload, signature, patterns, problems)
    if not tag.taggers:
        problems.append(f"{label}: has no tagger")
    for email in tag.taggers:
        if email is None:
            problems.append(f"{label}: tagger has no email")
        else:
            check_email(f"{label} tagger", email, problems)


def check_commit(short, raw, patterns, problems):
    """Every part of a commit object (see gitfiles.parse_commit). Labels use
    the short id and the part's role, never a header name or person."""
    label = f"commit {short}"
    commit = gitfiles.parse_commit(raw)
    check_text(f"{label} headers", commit.text, patterns, problems)
    for number, (payload, armored) in enumerate(commit.signatures, 1):
        check_signature(f"{label} signature {number}", payload, armored, patterns, problems)
    for role, name, email in commit.idents:
        check_ident(f"{label} {role}", name, email, patterns, problems)
    for number, embedded in enumerate(commit.mergetags, 1):
        tag, _ = gitfiles.parse_tag(short, embedded)
        check_tag(f"{label} mergetag {number}", tag, patterns, problems)
    # The message exactly as stored, so every encoding view applies.
    check_text(f"{label} message", commit.message, patterns, problems)
    if commit.encoding is not None:
        # Also read the names, emails and message in the encoding the
        # commit declares.
        names = b"\n".join(part for _, name, email in commit.idents for part in (name, email))
        check_declared(label, names + b"\n" + commit.message, commit.encoding, patterns, problems)


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


def commit_encoding():
    """The i18n.commitEncoding git will declare in the commit's `encoding`
    header (-c values included), or None if it is not set."""
    result = subprocess.run([gitfiles.git_exe(), "config", "-z", "--get", "i18n.commitEncoding"],
                            capture_output=True)
    if result.returncode == 1:
        return None
    if result.returncode != 0 or not result.stdout.endswith(b"\0"):
        sys.exit("guard: refusing, 'git config' failed (fetch or check the repository)")
    return result.stdout[:-1].decode("ascii", errors="replace")


def mode_staged(patterns):
    problems = []
    with gitfiles.Blobs() as blobs:
        check_entries("", gitfiles.staged(), patterns, problems, blobs)
    parts = []
    for role, variable in (("author", "GIT_AUTHOR_IDENT"), ("committer", "GIT_COMMITTER_IDENT")):
        # The configured identity is what goes into the commit (it reflects
        # --author), read with the same strict parse as pushed commits.
        ident = gitfiles.IDENT.fullmatch(git("var", variable).rstrip(b"\r\n"))
        if ident is None:
            problems.append(f"{role}: could not read the configured identity, refused")
            continue
        name, email = ident.group(1) or b"", ident.group(2)
        check_ident(role, name, email, patterns, problems)
        parts += [name, email]
    encoding = commit_encoding()
    if encoding is not None:
        # Also in the encoding the commit will declare (as for pushed commits).
        check_declared("author and committer", b"\n".join(parts), encoding, patterns, problems)
    return problems


def mode_message(patterns, message_file):
    problems = []
    with open(message_file, "rb") as handle:
        raw = handle.read()
    # The whole message, comment lines included (git keeps "#" lines in some
    # cleanup modes), as raw bytes so every encoding view applies.
    check_text("commit message", raw, patterns, problems)
    # git stores the message bytes as written and declares this encoding
    # for them, so read them in it too (the pushed-commit check does).
    encoding = commit_encoding()
    if encoding is not None:
        check_declared("commit message", raw, encoding, patterns, problems)
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
        [gitfiles.git_exe(), "cat-file", "--batch"],
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
        bodies[sha] = raw  # the whole commit object: headers and message
    return bodies


def mode_commits(patterns, revision_range):
    """Check every commit, not just the final files: a leak added and then
    removed in the same push would otherwise stay public in history."""
    problems = []
    # Annotated tags being pushed: check each tag object whole (message, tag
    # name, tagger, signature) and every tagger email. Labels use the short
    # id only, since a tag name could match a private pattern.
    for revision in gitfiles.require_commits(revision_range.split()):
        if revision.startswith("^"):
            continue  # already on the remote
        for tag in gitfiles.tag_chain(revision):
            check_tag(f"tag {tag.sha[:10]}", tag, patterns, problems)
    # Each commit is read whole from git (names, emails, every header and
    # the message), not through git log's formatted fields.
    # rev-list, not log: log.showSignature=true would add signature lines.
    shas = git("rev-list", revision_range).decode("ascii").split()
    bodies = commit_bodies(shas)
    with gitfiles.Blobs() as blobs:
        for sha in shas:
            short = sha[:10]
            check_commit(short, bodies[sha], patterns, problems)
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
