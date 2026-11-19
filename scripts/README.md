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
guard refuses code or config containing Business Source License text,
addresses that exist only in MetaDAO's BSL-era programs (their program IDs
and hard-coded admin keys), or MetaDAO's npm packages. Markdown is skipped,
because our docs discuss MetaDAO's license and programs by name.

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

It runs **on every commit** (in the pre-commit hook, after the leak guard),
**before every push** over each commit being pushed (so commits made by
merges and rebases, which skip the pre-commit hook, are scanned too), and
**in CI on every push**, over the full history.

Install gitleaks **v8.30.1** once per machine, from the
[release page](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1),
check the download against the release's `checksums.txt`, and put the binary
on your `PATH`. Commits and pushes are refused until it is installed.

Transaction signatures look the same as Solana secret keys. If a real
signature must be quoted in a doc or test, add a `gitleaks:allow` comment on
that line, and only after checking it is not a key.
