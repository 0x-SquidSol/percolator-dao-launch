#!/usr/bin/env python3
"""JavaScript dependency audit gate. See scripts/README.md.

Reads `yarn audit --json` output and fails on any advisory that is not in
the reviewed allowlist (yarn-audit-allowlist.json), or when the audit did
not finish. Allowlist entries that no longer appear are reported so the
list can be trimmed.

Usage:
  yarn audit --json | js_audit.py <allowlist.json>
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

REQUIRED_FIELDS = ("id", "package", "severity", "reason")


def load_allowlist(path):
    with open(path, encoding="utf-8") as handle:
        entries = json.load(handle)
    if not isinstance(entries, list):
        raise ValueError("allowlist must be a JSON list")
    allowed = {}
    for entry in entries:
        missing = [f for f in REQUIRED_FIELDS if not str(entry.get(f, "")).strip()]
        if missing:
            raise ValueError(f"allowlist entry {entry!r} is missing {missing}")
        if entry["id"] in allowed:
            raise ValueError(f"allowlist lists {entry['id']} twice")
        allowed[entry["id"]] = entry
    return allowed


def read_audit(lines):
    """Returns ({advisory id: (package, severity, title)}, finished)."""
    advisories = {}
    finished = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = record.get("type")
        if kind == "error":
            return advisories, False
        if kind == "auditSummary":
            finished = True
        if kind == "auditAdvisory":
            advisory = record["data"]["advisory"]
            key = advisory.get("github_advisory_id") or f"npm-{advisory['id']}"
            advisories[key] = (
                advisory.get("module_name", "?"),
                advisory.get("severity", "?"),
                advisory.get("title", "?"),
            )
    return advisories, finished


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    try:
        allowed = load_allowlist(argv[1])
    except (OSError, ValueError) as error:
        print(f"js audit: bad allowlist: {error}", file=sys.stderr)
        return 1

    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    advisories, finished = read_audit(sys.stdin)
    if not finished:
        print("js audit: yarn audit did not finish; failing closed", file=sys.stderr)
        return 1

    new = {k: v for k, v in advisories.items() if k not in allowed}
    stale = sorted(k for k in allowed if k not in advisories)
    for key in stale:
        print(f"js audit: allowlisted {key} no longer appears; remove it", file=sys.stderr)
    if new:
        print("js audit: advisories not in the reviewed allowlist:", file=sys.stderr)
        for key, (package, severity, title) in sorted(new.items()):
            print(f"  {key} {package} ({severity}): {title}", file=sys.stderr)
        print("Fix them, or review and add them to the allowlist with a reason.",
              file=sys.stderr)
        return 1
    print(f"js audit: ok ({len(advisories)} known advisories, all reviewed)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
