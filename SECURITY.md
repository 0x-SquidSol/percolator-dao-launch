# Security policy

> [!CAUTION]
> Experimental, unaudited code. Nothing in this repository is deployed or
> holds funds, and nothing here is a promise that anything will launch. See
> the [README](README.md).

## Reporting a problem

**While nothing is deployed**, please report any bug, security issues
included, as a [GitHub issue](https://github.com/0x-SquidSol/percolator-dao-launch/issues).
No real funds are at risk, so open discussion helps more than secrecy.

A useful report includes:
- what is wrong, and why it matters;
- the file and lines involved;
- how to reproduce it (a failing test is ideal);
- a suggested fix, if you have one.

**Before any program here holds real funds**, this policy will change:
security issues will then go through GitHub's
[private vulnerability reporting](https://github.com/0x-SquidSol/percolator-dao-launch/security/advisories/new)
instead of public issues, so a serious bug is not visible to attackers
before it can be addressed. Ordinary bugs will stay in public issues.

## Scope

In scope: the code in this repository (`programs/`, `crates/`, `scripts/`,
`tests/`) and its documentation.

Out of scope: third-party programs and libraries we use but do not maintain,
such as Squads, Solana, Anchor and SPL Token. Please report those to their
maintainers.

## Rewards

There is no bug bounty. If one is ever offered, it will be announced in this
file.
