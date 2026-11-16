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

We are also exploring ideas for people who held the earlier pump.fun token
before it was disowned. These are ideas only and are **not commitments to
anyone**:
- a guaranteed slot in the raise;
- a milestone-released tranche;
- staking of the original token;
- redirecting creator fees into airdrops of the new token.

The full background, options, license analysis and costs are in
**[docs/research.md](docs/research.md)**.

## Current direction (working assumptions, not decisions)

| Area | Working assumption | Status |
|---|---|---|
| Overall route | Our own stack. No MetaDAO deployed programs, current code, or permission | Exploring |
| Futarchy core | Fork MetaDAO's **LGPL-3.0** release `v0.1` (Dec 2023) and modernize it; never use their later BSL code | Exploring |
| Other programs | Raise/escrow, AMM, milestone packages and staking written independently | Exploring |
| Treasury | Squads v4, which we would call but not copy, controlled by the DAO | Exploring |
| Admin control | No third-party admin keys. Programs made immutable or DAO-upgradeable after audit | Design goal |
| Audits | Escrow program audited before any raise. Everything else audited after a raise, alongside the perps audit. No mint until that audit passes | Exploring |
| Refund safety | Refunds if the minimum isn't met or a launch deadline is missed | Design goal |
| Liquidity | Seeded from the raise. Our AMM splits that pool into pass/fail pools during proposals | Exploring |
| Fees | Go to the DAO treasury, not to founders personally | Design goal |
| Legacy-holder ideas | Guaranteed allocation, milestone tranche, original-token staking, creator-fee airdrops | **Ideas only** |
| Open source | All program code public (an LGPL requirement, and needed for trust) | Design goal |

Fallback if futarchy proves impractical: SPL Governance (Realms) with staking-
based voting.

## Open questions

- Whether to go ahead with any of this at all.
- Raise minimum and maximum, the share of the raise seeded into liquidity, and
  the launch deadline.
- Whether and how to recognize legacy holders: snapshot rules, guarantee caps,
  tranche size, staking design.
- Audit firm, scope and timing. Subsidy options.
- Securities and tax counsel.
- The license for this repository's own code.

## Repository layout

```
docs/
  research.md   Research record: background, MetaDAO code map, options,
                license analysis, candidate architecture, audit costs, sources
README.md       This file: current direction and status
```

More will be added as the plan develops. Code, if any is ever written, will be
experimental until audited.

## Disclaimers

- **No offer or solicitation.** Nothing here is an offer to sell or a
  solicitation to buy any token or security.
- **Not advice.** Nothing here is legal, tax, financial, or investment advice.
- **Trademarks.** MetaDAO, Futardio and Backable are names of their respective
  owners. This project is not affiliated with or endorsed by them.
