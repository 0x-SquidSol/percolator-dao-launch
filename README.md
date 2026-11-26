# percolator-dao-launch

> [!WARNING]
> **Experimental. Not confirmed. Nothing here is a promise.**
>
> This repository is an open brainstorm about how an independent,
> market-governed raise for Percolator *could* work. It is **not** an
> announcement, and it is **only one of several routes we are exploring**.
>
> - **Even if this is fully designed, built and audited, we may never use
>   it.**
> - There is **no confirmed** raise, token, sale, airdrop, allocation, staking
>   program, or distribution to holders of any token, past or present.
> - That stays true **no matter how much of this gets designed, written, or
>   built**. A design or working code here does not mean it will launch.
> - Every idea here may change completely or be dropped without notice.
> - **Do not buy, hold, sell, or keep any token because of this repository.**
>
> Any real launch would be announced only through Percolator's official
> channels, with final terms. Until then, assume none of this will happen.

## What this is

Percolator is a perpetuals protocol on Solana, pre-mainnet. We are exploring
whether we could run our own raise with safety properties similar to MetaDAO's,
but **without depending on any third party's code, admin keys, or permission**:

- **Funds escrowed**, with a minimum and automatic refunds.
- **One price for everyone.**
- **A treasury governed by markets (futarchy)**, not by the team.
- **Team tokens released only at price milestones.**
- **Liquidity seeded from the raise**, with trading fees going to the DAO
  treasury.

We are also exploring ideas around the earlier pump.fun token. These are ideas
only and are **not commitments to anyone**:
- for wallets in pre-crash / pre-announcement snapshots: a guaranteed slot in
  the raise and a milestone-released tranche, sized by a published formula;
- for *current* holders of the old token, and only if they vote for it:
  redirecting creator fees into weekly airdrops of the new token.

(Staking the original token was considered and dropped.)

- **[docs/plan.md](docs/plan.md)**: the start-to-finish working plan for this
  route, with every working assumption.
- **[docs/research.md](docs/research.md)**: background, options, license
  analysis and costs.

## Current direction (working assumptions, not decisions)

| Area | Working assumption | Status |
|---|---|---|
| Overall route | Our own stack. No MetaDAO deployed programs, current code, or permission | Exploring |
| Futarchy core | Fork MetaDAO's **LGPL-3.0** release `v0.1` (Dec 2023) and modernize it; never use their later BSL code | Exploring |
| Other programs | Raise/escrow, AMM, milestone packages and allowance rules written independently | Exploring |
| Treasury | Squads v4, which we would call but not copy, controlled by the DAO | Exploring |
| Admin control | No third-party admin keys. Upgrades only through DAO governance with a 7-day delay | Design goal |
| Raise | $250K min / $750K max, 7 days, one price for all (raise ÷ 10M buyer tokens) | Working assumption |
| Supply | Buyers 40%, team 40% (milestones, 12-month lock), legacy tranche 8% (milestones), liquidity 12% | Working assumption |
| Audits | Escrow audited before any raise. DAO programs audited after a raise, before any token exists. Perps audit paid later by an automatic treasury rule | Exploring |
| Refund safety | Refunds if the minimum isn't met or launch misses a 3-month deadline | Design goal |
| Liquidity | 20% of the raise seeded into a DAO-owned pool. Our AMM splits it into pass/fail pools during proposals | Exploring |
| Fees | Go to the DAO treasury, not to founders personally | Design goal |
| Team spending | Fixed monthly allowance with a "savings bank". Anything more needs governance | Working assumption |
| Legacy-holder ideas | Guaranteed raise slots and a milestone tranche (snapshot-based). Creator-fee airdrops only if current holders vote for them | **Ideas only** |
| Open source | All program code public (an LGPL requirement, and needed for trust) | Design goal |

Fallback if futarchy proves impractical: SPL Governance (Realms) with staking-
based voting.

## Open questions

- Whether to go ahead with any of this at all.
- Exact legacy-list minimums and exclusion rules (after reviewing the data).
- Audit firms, quotes and subsidy options.
- Securities and tax counsel. Legal wrapper.
- The license for this repository's own code.

The full list is in [docs/plan.md §19](docs/plan.md#19-open-items).

## Code in this repository

> [!CAUTION]
> **Experimental, unaudited code. Do not use it.**
>
> Code for this experiment is developed in the open, in this repository.
> - Code here is **work in progress and unaudited**. It may contain serious
>   bugs and may change or be deleted at any time.
> - **Code existing here does not mean anything will launch.** Writing,
>   testing or even auditing it is part of the experiment, not a commitment.
> - **Do not deploy it, connect funds to it, or rely on it** for anything.
> - Anything deployed by anyone other than Percolator's official channels is
>   **not ours**.

## Repository layout

```
.githooks/     Git hooks: leak, provenance and secret checks (setup: scripts/README.md)
.github/       CI workflows
crates/        Shared Rust code (claim-list check, fixed durations)
docs/          Working plan, research record and specifications (docs/spec/)
programs/      On-chain programs (only a README for now)
scripts/       Leak and license guards, spec reference code, test helpers
tests/         TypeScript tests and their helpers
NOTICE         Copyright, license status, trademarks
PROVENANCE.md  Where outside code comes from
SECURITY.md    How to report problems
README.md      This file: current direction and status
```

Other top-level files are build and tool settings.

As the experiment progresses, more folders may be added, such as a client
library, data tooling and a web app. Each will carry its own experimental
notice.

## Disclaimers

- **No offer or solicitation.** Nothing here is an offer to sell or a
  solicitation to buy any token or security.
- **Not advice.** Nothing here is legal, tax, financial, or investment advice.
- **Trademarks.** MetaDAO, Futardio and Backable are names of their respective
  owners. This project is not affiliated with or endorsed by them.
