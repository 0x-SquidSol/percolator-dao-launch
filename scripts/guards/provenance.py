#!/usr/bin/env python3
"""Provenance guard: refuse MetaDAO code released under the Business Source
License (BSL). See PROVENANCE.md and scripts/README.md.

Only MetaDAO's LGPL releases (tag v0.1) may be used here. This guard fails
when code or config contains:
  - BSL license text;
  - addresses that exist only in MetaDAO's BSL-era programs (their program
    IDs and hard-coded admin keys);
  - MetaDAO's published npm packages, which are built from the BSL code.

Every file is checked, in every readable view (see textscan.py), so text in
UTF-16, other encodings or binary files is checked too. Matching is per line.

Docs may discuss the license: the loose phrases "Business Source License
1.1" and "Additional Use Grant" are allowed only in the exact files in
LICENSE_DISCUSSION, and only in their plain UTF-8 view. Wording that only a
real copy of the license contains (its title alone on a line, its parameter
lines, its MariaDB copyright line, BUSL-1.1, "Licensor: MetaDAO") and every
address and npm marker are checked in every file, with no exceptions. This
file and its tests are skipped by exact path because they hold the markers.

It is a tripwire, not proof of clean authorship: a phrase split across two
lines, or reworded, is not caught.

Usage:
  provenance.py tree                     every file in the index (as stored)
  provenance.py staged                   staged changes (pre-commit hook)
  provenance.py commits <rev-list args>  files added or changed by each
                                         commit, as of that commit (pre-push
                                         hook and CI), so material added and
                                         later removed is still caught
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

import re  # noqa: E402
import subprocess  # noqa: E402

textscan = load_sibling("textscan")  # before gitfiles, which imports it
gitfiles = load_sibling("gitfiles")

# (label, pattern, allowed in LICENSE_DISCUSSION files)
MARKERS = [
    # Only in real copies of the license: blocked everywhere.
    ("BSL license text", re.compile(r"\bBUSL-1\.1\b", re.I), False),
    ("BSL license text", re.compile(r"Licensor:\s+MetaDAO", re.I), False),
    ("BSL license text", re.compile(r"MariaDB\s+Corporation", re.I), False),
    ("BSL license text", re.compile(r"^[\s#>*_]*Business\s+Source\s+License\s+1\.1[\s*_]*$", re.I), False),
    # Parameter lines whose names appear in little but the BSL itself.
    # ("Change Date" and a bare "Licensor" are left out: changelogs and
    # other licenses use them. "Licensor: MetaDAO" has its own marker.)
    ("BSL license text", re.compile(
        r"^[\s>*_|-]*(Licensed\s+Work|Additional\s+Use\s+Grant|Change\s+License)"
        r"[\s*_]*[:|]", re.I), False),
    # Loose mentions: allowed only where the license is discussed.
    ("BSL license text", re.compile(r"Business\s+Source\s+License\s+1\.1", re.I), True),
    ("BSL license text", re.compile(r"Additional\s+Use\s+Grant", re.I), True),
    ("MetaDAO npm package", re.compile(r"@metadaoproject/", re.I), False),
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
    # Case-sensitive: base58 addresses differ by case.
    MARKERS.append(("MetaDAO BSL-era address", re.compile(re.escape(address)), False))

# Exact paths only. These hold the markers themselves.
SKIPPED = frozenset({
    "scripts/guards/provenance.py",
    "scripts/guards/test_provenance.py",
    "scripts/guards/test_provenance_encodings.py",
})

# Exact paths of docs that discuss MetaDAO's license (loose mentions only).
LICENSE_DISCUSSION = frozenset({"docs/research.md"})

# A license file can never be exempt, whatever its extension.
LICENSE_NAME = re.compile(r"(?i)^(un)?licen[cs]e|^notice|^copying|^copyright")


def check_exemptions(paths):
    """Refuses to run if a license-discussion exception is not a doc under
    docs/ or is named like a license file."""
    for exempt in paths:
        if not exempt.startswith("docs/") or LICENSE_NAME.search(exempt.rsplit("/", 1)[-1]):
            sys.exit(f"provenance: refusing, {exempt} cannot be a license-discussion exception")


check_exemptions(LICENSE_DISCUSSION)


def git(*args):
    result = subprocess.run([gitfiles.git_exe(), *args], capture_output=True)
    if result.returncode != 0:
        sys.exit(f"provenance: git {args[0]} failed")
    return result.stdout


def check_listing(prefix, listing, problems, blobs):
    """Checks entries from gitfiles by their stored content, and reports
    every refusal (submodules, unmerged or unknown entries)."""
    entries, refusals = listing
    for refusal in refusals:
        # The name isn't printed: it could match a private pattern, which
        # only the leak guard can hide (it reports the same refusal first).
        problems.append(f"{prefix}an entry was refused: {refusal.reason}")
    for entry in entries:
        if entry.path in SKIPPED:
            continue
        data = blobs.read(entry.sha)
        found = []
        if data is None:
            found.append(f"{entry.path}: too large to inspect (over 25 MB)")
        else:
            check(entry.path, data, found)
        problems.extend(f"{prefix}{problem}" for problem in found)


def check_commits(rev_list_args, problems):
    gitfiles.require_commits(rev_list_args)
    commits = git("rev-list", *rev_list_args).decode("utf-8").split()
    with gitfiles.Blobs() as blobs:
        for commit in commits:
            check_listing(f"{commit[:12]} ", gitfiles.in_commit(commit), problems, blobs)


def check(path, data, problems):
    if path in SKIPPED:
        return
    if len(data) > textscan.MAX_SCAN_BYTES:
        problems.append(f"{path}: too large to inspect (over 25 MB)")
        return
    discussion = path in LICENSE_DISCUSSION
    reported = set()  # markers already reported for this file
    for view, text in textscan.text_views(data):
        for number, line in enumerate(text.splitlines(), start=1):
            for index, (label, pattern, discussable) in enumerate(MARKERS):
                if view and index in reported:
                    continue
                if discussion and discussable and not view:
                    continue  # a loose mention in a license-discussion doc
                if pattern.search(line):
                    reported.add(index)
                    message = (f"{path}: {label} (read as {view})" if view
                               else f"{path}:{number}: {label}")
                    if message not in problems:  # two markers can hit one line
                        problems.append(message)


def main(argv):
    mode = argv[1] if len(argv) >= 2 else ""
    problems = []
    if mode == "commits" and len(argv) >= 3:
        check_commits(argv[2:], problems)
    elif len(argv) != 2:
        sys.exit(__doc__)
    elif mode == "tree":
        with gitfiles.Blobs() as blobs:  # every file in the index, as stored
            check_listing("", gitfiles.in_index(), problems, blobs)
    elif mode == "staged":
        with gitfiles.Blobs() as blobs:
            check_listing("", gitfiles.staged(), problems, blobs)
    else:
        sys.exit(__doc__)
    if problems:
        print("provenance: possible BSL-licensed MetaDAO material:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print("Only MetaDAO's LGPL releases may be used. See PROVENANCE.md.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
