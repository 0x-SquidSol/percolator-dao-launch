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

Docs may discuss the license: loose mentions of its name and of its
extra-use grant are allowed only in the exact files in LICENSE_DISCUSSION,
and only in their plain UTF-8 view. Wording that only a real copy of the
license contains (its title alone on a line, its parameter lines, its
MariaDB copyright line, its SPDX identifier, its licensor line naming
MetaDAO) and every address and npm marker are checked in every file, with
no exceptions. That includes this file and its tests: they never spell a
marker out in one piece, and a test checks it. The only exception is
history: `commits` skips the exact earlier versions listed in HISTORICAL.

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
    # other licenses use them. The licensor line naming MetaDAO has its own marker.)
    ("BSL license text", re.compile(
        r"^[\s>*_|-]*(Licensed\s+Work|Additional\s+Use\s+Grant|Change\s+License)"
        r"[\s*_]*[:|]", re.I), False),
    # Loose mentions: allowed only where the license is discussed.
    ("BSL license text", re.compile(r"Business\s+Source\s+License\s+1\.1", re.I), True),
    ("BSL license text", re.compile(r"Additional\s+Use\s+Grant", re.I), True),
    ("MetaDAO npm package", re.compile(r"@metadaoproject[/]", re.I), False),
]

# Program IDs and hard-coded admin keys from MetaDAO's BSL-era programs
# (develop branch, checked 2026-11-19). Third-party addresses those programs
# also use (USDC, Meteora, Squads, ...) are deliberately not listed.
# Each is written in two pieces after its first four characters (Python joins
# adjacent strings), so this file does not match itself.
BSL_ADDRESSES = [
    "FUTA" "RELBfJfQ8RDGhg1wdhddq1odMAJUePHFuBYfUxKq",  # futarchy
    "VLTX" "1ishMBbcX3rdBWGssxawAo1Q2X2qxYFYqiGodVg",  # conditional_vault v0.4
    "moon" "tUzsdepotRGe5xsfip7vLPTJnVuafqdUWexVnPM",  # launchpad v0.7
    "MooN" "yh4CBUYEKyXVnjGYQ8mEiJDpGvJMdvrZx1iGeHV",  # launchpad
    "moon" "DJUoHteKkGATejA5bdJVwJ6V6Dg74gyqyJTx73n",  # launchpad
    "WALL" "8ucBuUyL46QYxwYJjidaFYhdvxUFrgvBxPshERx",  # bid_wall
    "pbPP" "QH7jyKoSLu8QYs3rSY3YkDRXEBojKbTgnUg7NDS",  # price_based_performance_package
    "pPV2" "pfrxnmstSb9j7kEeCLny5BGj6SNwCWGd6xbGGzz",  # performance_package_v2
    "gvnr" "27cVeyW3AVf3acL7VCJ5WjGAphytnsgcK1feHyH",  # mint_governor
    "LiQn" "owFbFQdYyZhF4pUbpsrZCjxRTQ1upKJxZ2VXjde",  # liquidation
    "GaTE" "jZy6eMdHg2BcL8dk3iE78jkJ9sPtyw1q2tMNi8PA",  # gated_mint
    "6awy" "HMshBGVjJ3ozdSJdyyDE1CTAXUwrpNMaRGMsb4sf",  # admin key
    "CWGa" "wadYU8CzRVBecnJymNw97H7E3ndDinV5sMzesgY2",  # admin key
    "tSTp" "6B6kE9o6ZaTmHm2ZwnJBBtgd3x112tapxFhmBEQ",  # fee recipient
    "HLnp" "Sz9h2S4hiLQ43rnSD9XkcUThA7B8hQMKmDaiTLcC",  # fee recipient
    "EP3S" "oC2SvR3d4c2eXVBvhEMWSr2j3YtoCY3UMiQV7BPD",  # DAO initializer key
]
for address in BSL_ADDRESSES:
    # Case-sensitive: base58 addresses differ by case.
    MARKERS.append(("MetaDAO BSL-era address", re.compile(re.escape(address)), False))

# Earlier versions of this file and its tests, which spelled the markers
# out: (path, git blob ID) pairs. Only `commits` skips them, and only at the
# same path, so old history can still be pushed. A blob ID is a hash of the
# content, so any change is checked in full. Never add to this.
HISTORICAL = frozenset({
    ("scripts/guards/provenance.py",
     "04ae6fdabd34243f12febeeecf564ef73dd64163"),
    ("scripts/guards/provenance.py",
     "1c0cc48a45e6372cee1026e2320bac9751def851"),
    ("scripts/guards/provenance.py",
     "6d7116e8565c307fb9716ddc65da953280ce373b"),
    ("scripts/guards/provenance.py",
     "817eb7f8bc70d307a32f385bcf7b4b704ff9a682"),
    ("scripts/guards/provenance.py",
     "8ba8891e2cfd56d5f5efb9f032e9b1b1852b8a22"),
    ("scripts/guards/provenance.py",
     "a2d441e31c14f0ca99cd10912c642ef66a77cf51"),
    ("scripts/guards/provenance.py",
     "f079d86f4117ca32eff2395a67c244fd3ad403db"),
    ("scripts/guards/test_provenance.py",
     "595ea60ee981e08c7c6041c24aa94c76aa2a6597"),
    ("scripts/guards/test_provenance.py",
     "a797238c55cfdc8bab6787a2f8379a52a2cf0d07"),
    ("scripts/guards/test_provenance.py",
     "e7c2326f6f8d6a5855d71d9fd4cfae162277d322"),
    ("scripts/guards/test_provenance_encodings.py",
     "8ef96adee5cd3117976463e964449f2e6ffb0528"),
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


def check_listing(prefix, listing, problems, blobs, historical=frozenset()):
    """Checks entries from gitfiles by their stored content, and reports
    every refusal (submodules, unmerged or unknown entries)."""
    entries, refusals = listing
    for refusal in refusals:
        # The name isn't printed: it could match a private pattern, which
        # only the leak guard can hide (it reports the same refusal first).
        problems.append(f"{prefix}an entry was refused: {refusal.reason}")
    for entry in entries:
        if (entry.path, entry.sha) in historical:
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
            check_listing(f"{commit[:12]} ", gitfiles.in_commit(commit), problems, blobs,
                          HISTORICAL)


def check(path, data, problems):
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
