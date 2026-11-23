# scripts

> [!CAUTION]
> Experimental, unaudited tooling for an experiment that may never be used.
> Nothing here means anything will launch.

## Leak guards (`guards/`)

This repository is public. These checks refuse commits that could leak
private material:

- paths containing "private", environment files, keypair and wallet files;
- content that looks like a Solana secret key;
- project-specific private patterns, loaded from a git-ignored local file or
  a CI secret, and never stored in this repository;
- commits whose author or committer email isn't a project address or a
  GitHub noreply address.

Messages never print the matched text (file names that match are hidden too),
so hook output and CI logs stay clean.

Both guards read file content from git itself (`guards/gitfiles.py`), never
from the working tree: `tree` checks every file in the index (what the next
commit publishes; in CI the same as the last commit), symlinks are checked
as the link text git stores, and changes of any kind except deletions are
checked, including a file's type changing. Submodules are refused on
purpose, because their content lives in another repository the guards
can't read, as are unmerged entries and anything git reports in an
unexpected way.

Content checks never skip a file for not being plain UTF-8: every file is
also read as UTF-16, UTF-32, Windows "ANSI" text and with NUL bytes removed
(`guards/textscan.py`), so text in other encodings and inside binary files is
checked too. Files over 25 MB are refused. Ordinary text costs the same as
before; large non-text files take longer (about two seconds per MB). Not
inspected yet: compressed or encoded content, such as zip-based formats, PDF
streams and base64.

They run in three places:
- **on every commit** (pre-commit and commit-msg hooks);
- **before every push** (pre-push hook): ref names, plus every commit being
  pushed, including its file names and contents, so a leak added and then
  removed before pushing is still caught;
- **in CI on every push**: the same checks again, plus every tracked file.

CI can only detect a leak after it is public, so the local hooks are the real
protection. Never bypass them with `--no-verify`.

### One-time setup per clone

```sh
sh scripts/guards/setup.sh
```

Then put the private patterns file, shared privately by a maintainer, at
`private/guard-patterns.txt`. Commits are refused until it exists.

### Self-tests

```sh
python -m unittest discover -s scripts/guards -p "test_*.py"
```

Each guard has a test that plants an example leak and checks it is blocked.

### Staging

Stage explicit paths (or use `git add -p`), and review `git diff --cached`
before committing. Avoid `git add -A` and `git add .`.

## Provenance guard (`guards/provenance.py`)

Only MetaDAO's LGPL releases may be used here (see `PROVENANCE.md`). This
guard refuses files containing Business Source License text, addresses that
exist only in MetaDAO's BSL-era programs (their program IDs and hard-coded
admin keys), or MetaDAO's npm packages. Every file is checked, in every
encoding view, like the leak guard.

Docs may *discuss* the license: naming it, or its extra-use grant, in a
sentence is allowed only in `docs/research.md` (an exact list in the guard,
which can never include a license-named file). Wording that only a real
copy of the license contains (its title on a line of its own, its parameter
lines, its copyright line, its SPDX identifier, its licensor line) and
every address and package name are refused in every file, with no
exceptions. The exact markers are in `guards/provenance.py`.

It runs **on every commit** (pre-commit hook), **before every push** over
each commit being pushed (including merges and rebases, which skip the
pre-commit hook), and **in CI on every push**, over every tracked file and
every pushed commit, so material added and later removed is still caught.
Its self-tests run with the leak guard's.

It is a tripwire for obvious copies, not proof of clean authorship: the
provenance rules and review still apply.

## Secret scan (gitleaks)

[gitleaks](https://github.com/gitleaks/gitleaks) looks for API keys, access
tokens and private keys. Settings live in `.gitleaks.toml`: gitleaks' built-in
rules plus a custom rule for Solana secret keys in their base58 text form,
which the built-in rules miss. Findings are redacted.

`guards/secretscan.py` runs gitleaks over the stored bytes of exactly the
files the leak guard checks, never over git's diff output: git settings
(`.gitattributes` `-diff` or `binary`, textconv, colour, merge display) change
that output and could hide a secret. Every scan also includes a test secret
that must be found, so a scan that read nothing never passes, and a committed
`.gitleaksignore` is not used.

The scan settings are never read from the working tree. A change is scanned
with the settings of reviewed `main` (a PR's base when that is `main`; `main`
before a push to `main`; the remote's current `main` for any other branch,
tag or PR, whose own earlier tip nobody reviewed) **and** with every
`.gitleaks.toml` the change itself brings, and a finding under any of them
counts. So a change can add rules but can't loosen its own scan: a loosened
setting only takes effect once it is on `main`. Other branches' settings
don't count. With no copy of `main` at hand the push and CI scans refuse:
push to a named remote (not a URL) whose `main` you have fetched. CI scans
every branch's files, so a branch holding a flagged line fails every CI run
until it is fixed with `gitleaks:allow`, merged or deleted. False positives
are allowed with a `gitleaks:allow` comment on the line itself. The push and
CI scans are the real gates; the commit-time scan is early feedback. Every
file version is read whole, so a file over 25 MB anywhere in history makes
the full-history scan refuse.

It runs **on every commit** (in the pre-commit hook, after the leak guard),
**before every push** over each commit being pushed (so commits made by
merges and rebases, which skip the pre-commit hook, are scanned too), and
**in CI on every push**, over the full history.

Install gitleaks **v8.30.1** once per machine, from the
[release page](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1),
check the download against the release's `checksums.txt`, and put the binary
on your `PATH`. Commits and pushes are refused until it is installed. Only
absolute `PATH` folders are searched, never the current folder, and a
gitleaks inside the repository is refused, so files in the repository can't
choose their own scanner.

Transaction signatures look the same as Solana secret keys. If a real
signature must be quoted in a doc or test, add a `gitleaks:allow` comment on
that line, and only after checking it is not a key.

## JavaScript dependency audit (`guards/js_audit.py`)

CI runs `yarn audit` and fails on any known advisory that is not in
`yarn-audit-allowlist.json`, the reviewed list of advisories we cannot fix
yet. Every entry names the advisory, the package, its severity and why it is
accepted. The audit also fails if `yarn audit` did not finish, so a network
error never counts as a pass. Entries that no longer appear are reported so
the list can be trimmed.

To check locally (Linux/WSL):

```sh
yarn audit --json | python3 scripts/guards/js_audit.py yarn-audit-allowlist.json
```

Before adding an entry, try to fix it first: a newer version of the package
that pulls it in, or a `resolutions` entry in `package.json`.
