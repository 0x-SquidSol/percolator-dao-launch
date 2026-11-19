#!/usr/bin/env python3
"""JavaScript dependency audit gate. See scripts/README.md.

Reads `yarn audit --json` output and fails on any advisory that is not in
the reviewed allowlist (yarn-audit-allowlist.json), or when the audit did
not finish. Allowlist entries that no longer appear are reported so the
list can be trimmed.

Usage:
  yarn audit --json | js_audit.py <allowlist.json>
"""
import json
import sys

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
