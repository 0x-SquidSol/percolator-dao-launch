#!/usr/bin/env python3
"""Provenance guard: refuse MetaDAO code released under the Business Source
License (BSL). See PROVENANCE.md and scripts/README.md.

Only MetaDAO's LGPL releases (tag v0.1) may be used here. This guard fails
when code or config contains:
  - BSL license text;
  - addresses that exist only in MetaDAO's BSL-era programs (their program
    IDs and hard-coded admin keys);
  - MetaDAO's published npm packages, which are built from the BSL code.

Markdown is skipped: our docs discuss MetaDAO's license and programs by
name. This file and its tests are skipped because they hold the markers.

Usage:
  provenance.py tree     every tracked file
  provenance.py staged   staged changes (used by the pre-commit hook)
"""
import re
import subprocess
import sys

MARKERS = [
    ("BSL license text", re.compile(r"Business Source License 1\.1")),
    ("BSL license text", re.compile(r"\bBUSL-1\.1\b")),
    ("BSL license text", re.compile(r"Additional Use Grant")),
    ("BSL license text", re.compile(r"Licensor:\s+MetaDAO")),
    ("MetaDAO npm package", re.compile(r"@metadaoproject/")),
]

# Program IDs and hard-coded admin keys from MetaDAO's BSL-era programs
# (develop branch, checked 2026-11-19). Third-party addresses those programs
# also use (USDC, Meteora, Squads, ...) are deliberately not listed.
BSL_ADDRESSES = [
    "FUTARELBfJfQ8RDGhg1wdhddq1odMAJUePHFuBYfUxKq",  # futarchy
    "VLTX1ishMBbcX3rdBWGssxawAo1Q2X2qxYFYqiGodVg",  # conditional_vault v0.4
    "moontUzsdepotRGe5xsfip7vLPTJnVuafqdUWexVnPM",  # launchpad v0.7
    "MooNyh4CBUYEKyXVnjGYQ8mEiJDpGvJMdvrZx1iGeHV",  # launchpad
    "moonDJUoHteKkGATejA5bdJVwJ6V6Dg74gyqyJTx73n",  # launchpad
    "WALL8ucBuUyL46QYxwYJjidaFYhdvxUFrgvBxPshERx",  # bid_wall
    "pbPPQH7jyKoSLu8QYs3rSY3YkDRXEBojKbTgnUg7NDS",  # price_based_performance_package
    "pPV2pfrxnmstSb9j7kEeCLny5BGj6SNwCWGd6xbGGzz",  # performance_package_v2
    "gvnr27cVeyW3AVf3acL7VCJ5WjGAphytnsgcK1feHyH",  # mint_governor
    "LiQnowFbFQdYyZhF4pUbpsrZCjxRTQ1upKJxZ2VXjde",  # liquidation
    "GaTEjZy6eMdHg2BcL8dk3iE78jkJ9sPtyw1q2tMNi8PA",  # gated_mint
    "6awyHMshBGVjJ3ozdSJdyyDE1CTAXUwrpNMaRGMsb4sf",  # admin key
    "CWGawadYU8CzRVBecnJymNw97H7E3ndDinV5sMzesgY2",  # admin key
    "tSTp6B6kE9o6ZaTmHm2ZwnJBBtgd3x112tapxFhmBEQ",  # fee recipient
    "HLnpSz9h2S4hiLQ43rnSD9XkcUThA7B8hQMKmDaiTLcC",  # fee recipient
    "EP3SoC2SvR3d4c2eXVBvhEMWSr2j3YtoCY3UMiQV7BPD",  # DAO initializer key
]
for address in BSL_ADDRESSES:
    MARKERS.append(("MetaDAO BSL-era address", re.compile(re.escape(address))))

SKIPPED = re.compile(
    r"(?i)(\.md$|^scripts/guards/provenance\.py$|^scripts/guards/test_provenance\.py$)"
)


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True)
    if result.returncode != 0:
        sys.exit(f"provenance: git {args[0]} failed")
    return result.stdout


def tracked_files():
    return [p for p in git("ls-files", "-z").decode("utf-8").split("\0") if p]


def staged_files():
    out = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
    return [p for p in out.decode("utf-8").split("\0") if p]


def check(path, data, problems):
    if SKIPPED.search(path) or b"\0" in data:
        return
    text = data.decode("utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in MARKERS:
            if pattern.search(line):
                problems.append(f"{path}:{number}: {label}")


def main(argv):
    mode = argv[1] if len(argv) == 2 else ""
    problems = []
    if mode == "tree":
        for path in tracked_files():
            data = read(path)
            if data is not None:
                check(path, data, problems)
    elif mode == "staged":
        for path in staged_files():
            check(path, git("show", f":{path}"), problems)
    else:
        sys.exit(__doc__)
    if problems:
        print("provenance: possible BSL-licensed MetaDAO material:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print("Only MetaDAO's LGPL releases may be used. See PROVENANCE.md.", file=sys.stderr)
        return 1
    return 0


def read(path):
    """Working-tree content of a tracked file, or None if it is deleted."""
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except FileNotFoundError:
        return None


if __name__ == "__main__":
    sys.exit(main(sys.argv))
