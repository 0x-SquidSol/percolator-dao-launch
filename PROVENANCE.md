# Provenance log

> [!CAUTION]
> Experimental, unaudited code. See the [README](README.md).

This log records where code in this repository comes from, so anyone can
check that it was written here or taken from sources whose licenses allow
it.

## Rules

1. **Written here by default.** Any file not listed below was written for
   this repository.
2. **Every file derived from outside code is listed**, with the source
   repository, the exact commit, its license, and what was changed.
3. **Copied code is imported unchanged first**, in its own commit, and only
   modified in later commits, so each change can be reviewed against the
   original.
4. **MetaDAO code:** only the LGPL-3.0 releases may be used, in practice tag
   `v0.1` (commit `a9eaaf5`, December 2023). MetaDAO code released under the
   Business Source License (from commit `5452889` onward) is **never** copied,
   adapted or paraphrased here. See [docs/research.md](docs/research.md) for
   the license analysis.
5. **Programs we call but do not copy** (for example Squads v4) are listed
   too. Their binaries are fetched by checked fingerprint for tests and never
   committed.
6. **LGPL obligations** for derived files: keep the original copyright and
   license notices, mark the file as modified, and keep the modified source
   public.

## Derived files

| Path | Source | Exact version | License | Changes |
|---|---|---|---|---|
| *(none yet)* | | | | |

## Programs called but not copied

| Program | Used for | Source | License | How it is obtained |
|---|---|---|---|---|
| *(none yet)* | | | | |
