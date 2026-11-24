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
  - The settings (.gitleaks.toml) never come from the working tree: a
    trusted revision's version and every version the change brings are all
    used, and a finding under any of them counts (see listing), so a change
    can't loosen its own scan.

Fails closed: gitleaks missing or failing, a missing or inconsistent report,
a file gitfiles can't check, a file too large to read, no settings to scan
with, or a settings rule that matches on paths. Findings print the short
commit, rule and line, and the path unless it could be private.

Usage:
  secretscan.py staged                 the staged changes (pre-commit)
  secretscan.py commits --trusted REV [--change REV2] <revisions>
                                       every commit in a range (pre-push, CI),
                                       e.g. a..b, a single id, or --all;
                                       REV is reviewed main, REV2 the commit
                                       whose settings changes count
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

import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402

load_sibling("textscan")  # before gitfiles, which imports it
gitfiles = load_sibling("gitfiles")  # also switches off git replace stand-ins

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
        try:
            with open(PATTERNS_FILE, encoding="utf-8") as handle:
                raw = handle.read()
        except (OSError, UnicodeDecodeError):
            return None
    lines = [line.strip() for line in (raw or "").splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    try:
        return [re.compile(line, re.IGNORECASE) for line in lines] or None
    except (re.error, OverflowError, RecursionError):  # e.g. a{99999999999}
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


def check_config(data):
    """Rules of our own that match on paths can't be checked this way (the
    content copy has no path, the marker has no content), so refuse them
    rather than silently drop them."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        refuse(f"a version of {CONFIG} is not valid UTF-8")
    if re.search(r"""(?m)^\s*(?:["']path["']|path)\s*=""", text):
        refuse(f"{CONFIG} has a path-based rule, which this scan does not support")


def config_blobs(revisions):
    """Blob ids of .gitleaks.toml in each revision ("" means the index) that
    has one."""
    if not revisions:
        return set()
    query = "".join(f"{revision}:{CONFIG}\n" for revision in revisions).encode()
    result = subprocess.run([gitfiles.git_exe(), "cat-file", "--batch-check"], input=query,
                            capture_output=True)
    if result.returncode != 0:
        refuse("could not read the scan settings from git")
    blobs = set()
    for line in result.stdout.decode("utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob":
            blobs.add(parts[0])
        elif not line.endswith(" missing"):
            refuse(f"{CONFIG} in some revision is not a file")
    return blobs


def resolve(revision):
    """The commit id a revision names, or None."""
    result = subprocess.run([gitfiles.git_exe(), "rev-parse", "-q", "--verify", f"{revision}^{{commit}}"],
                            capture_output=True)
    return result.stdout.decode("ascii").strip() if result.returncode == 0 else None


def listing(mode, args):
    """[(label, Entry)] for every file to scan, and the blob ids of every
    .gitleaks.toml version to scan them with.

    The settings never come from the working tree, which the change being
    checked controls. They come from an already-trusted revision plus every
    version the change brings, and a finding under any of them counts, so a
    change can add rules but never loosen its own scan:
      staged:  HEAD's, the upstream branch's and origin/main's settings,
               and the staged ones;
      commits: --trusted REV's settings (REV is reviewed main) and those of
               every commit the change brings that REV lacks; the change is
               --change REV2 if given (CI: the event's own commit, so other
               branches' settings don't count), else the scanned revisions.
               No --trusted: refused, as there is nothing reviewed to go by."""
    if mode == "staged":
        if args:
            refuse("'staged' takes no arguments")
        entries, refusals = gitfiles.staged()
        pairs = [("staged", entry) for entry in entries]
        reviewed = ("HEAD", "@{upstream}", "refs/remotes/origin/main")
        reviewed_revs = [rev for rev in map(resolve, reviewed) if rev]
        configs = config_blobs(reviewed_revs + [""])  # "" is the index
    else:
        options = {}
        while args[:1] in (["--trusted"], ["--change"]):
            if len(args) < 2:
                refuse(f"{args[0]} needs a revision")
            options[args[0]] = resolve(args[1])
            if options[args[0]] is None:
                refuse(f"the {args[0][2:]} revision is not a commit here")
            args = args[2:]
        trusted = options.get("--trusted")
        if trusted is None:
            refuse("no reviewed revision to take the scan settings from: push to a "
                   "named remote whose main you have fetched (or pass --trusted)")
        resolved = gitfiles.require_commits(args)
        shas = gitfiles._git("rev-list", *resolved).decode("ascii").split()
        pairs, refusals = [], []
        for sha in shas:
            entries, refused = gitfiles.in_commit(sha)
            refusals += refused
            pairs += [(sha[:10], entry) for entry in entries]
        configs = config_blobs([trusted])
        if not configs:
            refuse(f"the trusted revision has no {CONFIG}")
        change = [options["--change"]] if "--change" in options else resolved
        brought = gitfiles._git("rev-list", *change, "^" + trusted).decode("ascii").split()
        configs |= config_blobs(brought)
    if refusals:
        # Never name the files: their paths could be private.
        refuse(f"{len(refusals)} file(s) can't be checked (submodule, unmerged or unknown type)")
    if not configs:
        refuse(f"found no {CONFIG} to scan with")
    return pairs, sorted(configs)


def scan(pairs, configs, gitleaks):
    """Problems found by gitleaks (the binary at `gitleaks`) under any of the
    settings, as printable lines."""
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
            settings = []
            with gitfiles.Blobs() as blobs:
                for blob in configs:
                    data = blobs.read(blob)
                    if data is None:
                        refuse(f"a version of {CONFIG} is too large")
                    check_config(data)
                    path = os.path.join(tmp, f"settings-{blob}.toml")
                    with open(path, "wb") as handle:
                        handle.write(data)
                    settings.append(path)
        except OSError:
            refuse("could not prepare the files to scan")
        problems = []
        for number, config in enumerate(settings):
            report = os.path.join(tmp, f"report-{number}.json")
            try:
                result = subprocess.run(
                    [gitleaks, "dir", "--config", config, "--no-banner", "--redact",
                     "--log-level", "debug", "--gitleaks-ignore-path", no_ignores,
                     "--exit-code", str(LEAKS_EXIT), "--report-format", "json",
                     "--report-path", report, root],
                    capture_output=True,
                )
            except OSError:
                refuse("could not run gitleaks")
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
            problems += report_lines(findings, where, root, canary)
        return problems


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
        try:
            name = os.path.normcase(os.path.normpath(os.path.join(root, os.path.relpath(name, root))))
        except ValueError:  # a path on another drive (Windows)
            refuse("gitleaks skipped a file instead of scanning it")
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
            rule, line = finding["RuleID"], finding["StartLine"]
            if type(line) is not int:  # not 1.5, True, "3" or Infinity
                raise TypeError
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


def find_gitleaks():
    """gitleaks from an absolute PATH folder (see gitfiles.program): the
    repository being scanned must never choose its own scanner."""
    gitleaks = gitfiles.program("gitleaks")
    if gitleaks is None:
        refuse("gitleaks is required (see scripts/README.md)")
    return gitleaks


def main(argv):
    if len(argv) < 2 or argv[1] not in ("staged", "commits"):
        sys.exit(__doc__)
    gitleaks = find_gitleaks()  # before git is used
    os.chdir(gitfiles._git("rev-parse", "--show-toplevel").decode().strip())
    # Now from the top folder: neither program may come from the repository.
    places = [os.path.dirname(gitleaks), gitleaks,
              os.path.dirname(gitfiles.git_exe()), gitfiles.git_exe()]
    try:
        planted = any(gitfiles.in_current_folder(place) for place in places)
    except OSError:
        refuse("could not check where gitleaks and git are installed")
    if planted:
        refuse("gitleaks and git must not come from inside the repository")
    pairs, configs = listing(argv[1], argv[2:])
    problems = scan(pairs, configs, gitleaks)
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
