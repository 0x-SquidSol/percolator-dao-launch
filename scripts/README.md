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
