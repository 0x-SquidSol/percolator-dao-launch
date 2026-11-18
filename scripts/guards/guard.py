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
  guard.py tree              check every tracked file (CI)
  guard.py commits <range>   check messages and identities of commits (CI)
"""
import os
import re
import subprocess
import sys

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
        sys.exit("guard: git command failed: git " + " ".join(args))
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


def check_path(path, patterns, problems):
    for pattern, why in FORBIDDEN_PATHS:
        if pattern.search(path):
            problems.append(f"{path}: {why}")
    check_name(f"{path}: file name", path, patterns, problems)


def check_text(label, data, patterns, problems):
    if b"\0" in data[:8000]:
        return  # binary file
    text = data.decode("utf-8", errors="replace")
    if SECRET_KEY_ARRAY.search(text):
        problems.append(f"{label}: looks like a secret key (64-number array)")
    for number, line in enumerate(text.splitlines(), 1):
        for index, pattern in enumerate(patterns, 1):
            if pattern.search(line):
                problems.append(f"{label}:{number}: matches private pattern #{index}")


def check_email(label, email, problems):
    if not ALLOWED_EMAIL.search(email.strip()):
        problems.append(f"{label} email is not a project or GitHub noreply address")


def ident_email(variable):
    match = re.search(r"<([^>]*)>", git("var", variable).decode(errors="replace"))
    return match.group(1) if match else ""


def mode_staged(patterns):
    problems = []
    names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    for path in filter(None, names.decode("utf-8").split("\0")):
        check_path(path, patterns, problems)
        check_text(path, git("show", ":" + path), patterns, problems)
    check_email("author", ident_email("GIT_AUTHOR_IDENT"), problems)
    check_email("committer", ident_email("GIT_COMMITTER_IDENT"), problems)
    return problems


def mode_message(patterns, message_file):
    problems = []
    with open(message_file, "rb") as handle:
        text = handle.read().decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    check_text("commit message", "\n".join(lines).encode(), patterns, problems)
    branch = git("symbolic-ref", "--short", "-q", "HEAD", check=False).decode().strip()
    if branch:
        check_name("branch name", branch, patterns, problems)
    return problems


def mode_tree(patterns):
    problems = []
    for path in filter(None, git("ls-files", "-z").decode("utf-8").split("\0")):
        check_path(path, patterns, problems)
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                check_text(path, handle.read(), patterns, problems)
    return problems


def mode_commits(patterns, revision_range):
    problems = []
    log = git("log", "--format=%H%x00%ae%x00%ce%x00%B%x1e", revision_range)
    for record in filter(str.strip, log.decode("utf-8", errors="replace").split("\x1e")):
        sha, author, committer, body = record.strip("\n").split("\0", 3)
        short = sha[:10]
        check_email(f"commit {short} author", author, problems)
        check_email(f"commit {short} committer", committer, problems)
        check_text(f"commit {short} message", body.encode(), patterns, problems)
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
    else:
        sys.exit(__doc__)
    if problems:
        fail(problems)


if __name__ == "__main__":
    main(sys.argv)
