#!/usr/bin/env python3
"""Secret scan: gitleaks over the stored bytes of exactly the files the leak
guard checks (listed and read through gitfiles).

`gitleaks git` scans the patch text git prints, and git settings change that
text: diff attributes (`-diff`, `binary`, textconv), colour, merge and root
commit display, binary detection. So gitleaks never reads through git here:
each file's bytes are copied to a temporary folder and scanned there with
`gitleaks dir`, which no git setting reaches.

  - Content is copied under its blob id, so gitleaks' own path skips
    (lockfiles, images, ...) can't skip it.
  - A one-byte marker per file under its (cleaned) path lets gitleaks' rules
    that match on a file name alone (e.g. `.p12` key files) still fire.
  - A fake token is added to every scan and must be found, so a scan that
    silently read nothing (a config that allows everything, a gitleaks
    change) never passes.
  - A committed `.gitleaksignore` is never used.

Fails closed: gitleaks missing or failing, a missing or inconsistent report,
a file gitfiles can't check, a file too large to read, or a config rule that
matches on paths. Findings print the short commit, rule and line, and the
path unless it could be private.

Usage:
  secretscan.py staged                 the staged changes (pre-commit)
  secretscan.py commits <revisions>    every commit in a range (pre-push, CI),
                                       e.g. a..b, a single id, or --all
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gitfiles  # noqa: E402  (also switches off git replace stand-ins)

CONFIG = ".gitleaks.toml"
PATTERNS_FILE = os.path.join("private", "guard-patterns.txt")
LEAKS_EXIT = 3  # distinct from gitleaks' own error exit (1)
# A fake GitHub token, built from parts so this file doesn't match itself.
CANARY = ('github_pat = "' + "ghp_" + "Zq7Lw2Xc9Vb4Nm1Ka8Sd3Fg6Hj0Pt5Yr2Ue4" + '"\n').encode()
CANARY_NAME = "canary"
# gitleaks sniffs each file's type from its first bytes and skips "binary"
# types (PDF, ELF, zip, gzip, tar, ...) even when the rest is plain text.
# Every content copy starts with this plain-text block, longer than the
# deepest signature offset (ISO 9660: byte 32769), so the type is always
# text; reported lines are shifted back by its line count. Any skip that
# still happens is caught from gitleaks' log (see skipped_files).
HEADER_LINES = 512
HEADER = (b"#" * 79 + b"\n") * HEADER_LINES
# Windows can't create files with these names (in any case, with any suffix).
RESERVED = re.compile(r"(?i)^(con|prn|aux|nul|com\d|lpt\d)(\.|$)")
MAX_PART = 60
MAX_MARKER_PATH = 120


def refuse(why):
    sys.exit(f"secret scan: refusing, {why}")


def private_patterns():
    """The leak guard's private patterns, used only to hide paths in the
    report. None (hide every path) when they aren't available, as in CI's
    secret scan job, or can't be read."""
    raw = os.environ.get("GUARD_PATTERNS")
    if raw is None and os.path.isfile(PATTERNS_FILE):
        with open(PATTERNS_FILE, encoding="utf-8") as handle:
            raw = handle.read()
    lines = [line.strip() for line in (raw or "").splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    try:
        return [re.compile(line, re.IGNORECASE) for line in lines] or None
    except re.error:
        return None


def shown(path, patterns):
    if patterns is None or any(pattern.search(path) for pattern in patterns):
        return "<path hidden>"
    return path


def marker_path(path):
    """A safe relative path for the one-byte name marker: every part limited
    to [A-Za-z0-9._-] and cut from the front (so a long name keeps its
    extension), no '.'/'..', no trailing dot (Windows drops it), no Windows
    device names, and only the last parts kept (so the file name survives)
    within a short length."""
    parts = []
    for part in path.split("/"):
        clean = re.sub(r"[^A-Za-z0-9._-]", "_", part)[-MAX_PART:]
        if clean.endswith("."):
            clean += "_"
        if clean in ("", ".", "..") or RESERVED.match(clean):
            clean = "_" + clean
        parts.append(clean)
    kept, length = [], 0
    for part in reversed(parts):
        if kept and length + len(part) + 1 > MAX_MARKER_PATH:
            break
        kept.insert(0, part)
        length += len(part) + 1
    return os.path.join(*kept)


def check_config():
    """Rules of our own that match on paths can't be checked this way (the
    content copy has no path, the marker has no content), so refuse them
    rather than silently drop them."""
    try:
        with open(CONFIG, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        refuse(f"could not read {CONFIG}")
    if re.search(r"(?m)^\s*path\s*=", text):
        refuse(f"{CONFIG} has a path-based rule, which this scan does not support")


def listing(mode, args):
    """[(label, Entry)] for every file to scan."""
    if mode == "staged":
        if args:
            refuse("'staged' takes no arguments")
        entries, refusals = gitfiles.staged()
        pairs = [("staged", entry) for entry in entries]
    else:
        resolved = gitfiles.require_commits(args)
        shas = gitfiles._git("rev-list", *resolved).decode("ascii").split()
        pairs, refusals = [], []
        for sha in shas:
            entries, refused = gitfiles.in_commit(sha)
            refusals += refused
            pairs += [(sha[:10], entry) for entry in entries]
    if refusals:
        # Never name the files: their paths could be private.
        refuse(f"{len(refusals)} file(s) can't be checked (submodule, unmerged or unknown type)")
    return pairs


def scan(pairs):
    """Problems found by gitleaks, as printable lines."""
    gitleaks = shutil.which("gitleaks")
    if gitleaks is None:
        refuse("gitleaks is required (see scripts/README.md)")
    where = {}  # file in the scan folder -> [(label, path)]
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "scan")
        os.makedirs(os.path.join(root, "names"))
        try:
            with gitfiles.Blobs() as blobs:
                for number, (label, entry) in enumerate(pairs):
                    content = os.path.join(root, entry.sha)
                    if content not in where:
                        data = blobs.read(entry.sha)
                        if data is None:
                            refuse("a file is too large to scan (over 25 MB)")
                        with open(content, "wb") as handle:
                            handle.write(HEADER + data)
                        where[content] = []
                    where[content].append((label, entry.path))
                    marker = os.path.join(root, "names", entry.sha, str(number),
                                          marker_path(entry.path))
                    os.makedirs(os.path.dirname(marker), exist_ok=True)
                    with open(marker, "wb") as handle:
                        handle.write(b"x")  # gitleaks skips empty files
                    where[marker] = [(label, entry.path)]
            canary = os.path.join(root, CANARY_NAME)
            with open(canary, "wb") as handle:
                handle.write(HEADER + CANARY)  # written like every content copy
            no_ignores = os.path.join(tmp, "gitleaksignore")
            open(no_ignores, "w").close()
        except OSError:
            refuse("could not prepare the files to scan")
        report = os.path.join(tmp, "report.json")
        result = subprocess.run(
            [gitleaks, "dir", "--config", CONFIG, "--no-banner", "--redact",
             "--log-level", "debug", "--gitleaks-ignore-path", no_ignores,
             "--exit-code", str(LEAKS_EXIT), "--report-format", "json",
             "--report-path", report, root],
            capture_output=True,
        )
        if result.returncode not in (0, LEAKS_EXIT):
            refuse("gitleaks failed")
        check_log(result.stdout + result.stderr, root)
        try:
            with open(report, encoding="utf-8") as handle:
                findings = json.load(handle)
        except (OSError, ValueError):
            refuse("gitleaks wrote no readable report")
        if not isinstance(findings, list) or (result.returncode == LEAKS_EXIT) != bool(findings):
            refuse("gitleaks gave an inconsistent result")
        return report_lines(findings, where, root, canary)


ANSI = re.compile(rb"\x1b\[[0-9;]*m")
# gitleaks' logger quotes a value (Go string syntax) only when it has to:
# Windows paths always (backslashes), Linux paths only with spaces or quotes.
LOG_PATH = re.compile(rb'path=("(?:[^"\\]|\\.)*"|\S+)')


def log_path(value):
    """The path from a log value, or None if it can't be read exactly."""
    if not value.startswith(b'"'):
        return value.decode("utf-8", errors="strict")
    try:
        # Go's quoting is JSON's for the escapes it uses on paths (\\, \",
        # \uXXXX); anything else (\xNN) fails here and is refused.
        return json.loads(value.decode("utf-8"))
    except ValueError:
        return None


def check_log(log, root):
    """Refuses if gitleaks reported a warning or error, or skipped any file
    other than a name marker (whose content copy is scanned anyway): a
    skipped content copy (binary-looking, too large, allowlisted, unreadable)
    would otherwise pass silently."""
    markers = os.path.normcase(os.path.normpath(os.path.join(root, "names"))) + os.sep
    for line in ANSI.sub(b"", log).splitlines():
        words = line.split()
        level = words[1] if len(words) > 1 else b""
        expected = words[2:4] == [b"leaks", b"found:"] or b"skipping file" in line
        if level in (b"WRN", b"ERR", b"FTL") and not expected:
            refuse("gitleaks reported a problem while scanning")
        if b"skipping" not in line.lower():
            continue
        path = LOG_PATH.search(line)
        try:
            name = log_path(path.group(1)) if path else None
        except UnicodeDecodeError:
            name = None
        if name is None:
            refuse("gitleaks skipped a file it did not name")
        name = os.path.normcase(os.path.normpath(os.path.join(root, os.path.relpath(name, root))))
        if not name.startswith(markers):
            refuse("gitleaks skipped a file instead of scanning it")


def report_lines(findings, where, root, canary):
    def key(name):
        return os.path.normcase(os.path.normpath(name))

    patterns = private_patterns()
    places = {key(name): (name, found_in) for name, found_in in where.items()}
    markers = key(os.path.join(root, "names")) + os.sep
    problems, canary_found = [], False
    for finding in findings:
        try:
            found = key(os.path.join(root, os.path.relpath(finding["File"], root)))
            rule, line = finding["RuleID"], int(finding["StartLine"])
        except (KeyError, TypeError, ValueError):
            refuse("gitleaks gave an unreadable finding")
        if found == key(canary):
            canary_found = True
            continue
        if found not in places:
            refuse("gitleaks reported a file this scan did not write")
        if not found.startswith(markers):
            line -= HEADER_LINES  # content copies start with HEADER
        for label, path in places[found][1]:
            problems.append(f"{label} {shown(path, patterns)}:{line}: {rule}")
    if not canary_found:
        refuse("the scan's self-check failed (a test secret was not found)")
    return problems


def main(argv):
    if len(argv) < 2 or argv[1] not in ("staged", "commits"):
        sys.exit(__doc__)
    os.chdir(gitfiles._git("rev-parse", "--show-toplevel").decode().strip())
    check_config()
    pairs = listing(argv[1], argv[2:])
    problems = scan(pairs)
    if problems:
        print("secret scan: refusing, possible secrets found (redacted):", file=sys.stderr)
        for problem in sorted(set(problems)):
            print("  - " + problem, file=sys.stderr)
        print("A false positive needs a `gitleaks:allow` comment on that line, after review.",
              file=sys.stderr)
        sys.exit(1)
    print(f"secret scan: {len(pairs)} file version(s) clean", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv)
