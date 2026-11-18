# Research: an independent, futarchy-governed raise for Percolator

> [!WARNING]
> **Experimental brainstorming. Nothing here is confirmed or promised.**
> This repository explores *possible* ways an independent Percolator raise
> could work. It is one of several routes we are exploring. No raise, token,
> airdrop, allocation, staking program, or legacy-holder distribution is
> planned, scheduled, or guaranteed. Even if this is fully built, we may never
> use it. Ideas here may change completely or be dropped.
> **Do not buy, hold, or sell any token based on this repository.**

This document records research behind `percolator-dao-launch`: what we looked
at, what we found, which options we considered, and which direction we are
currently exploring. It is a research record, not a plan of record.

- **Status:** early exploration (November 2026).
- **Update:** later working assumptions are in [plan.md](plan.md) and replace
  parts of this record. In particular, **original-token staking (§7.4) was
  dropped**, and creator-fee airdrops (§7.5) would go to **current** old-token
  holders, only if they vote for it. Legacy-holder ideas would use
  pre-crash/pre-announcement snapshots and a published scoring formula.
- **Not legal, tax, or financial advice.** The license analysis below rests on
  the license texts and public repository history. Securities and tax questions
  still need counsel.

---

## Contents

1. [Background](#1-background)
2. [What we want](#2-what-we-want)
3. [How the MetaDAO raise system works (v0.8)](#3-how-the-metadao-raise-system-works-v08)
4. [Options we evaluated](#4-options-we-evaluated)
5. [License analysis](#5-license-analysis)
6. [The chosen architecture in detail](#6-the-chosen-architecture-in-detail)
7. [Making it right for legacy holders](#7-making-it-right-for-legacy-holders)
8. [Liquidity and fees](#8-liquidity-and-fees)
9. [Audit strategy and cost](#9-audit-strategy-and-cost)
10. [Risks and open questions](#10-risks-and-open-questions)
11. [Sources](#11-sources)

---

## 1. Background

- **Percolator** is a permissionless perpetuals protocol on Solana, currently
  pre-mainnet.
- An earlier pump.fun token, which graduated to PumpSwap, was associated with the
  project. The team has since disowned it. Holders who bought **before that
  announcement** were affected by how it happened. We are exploring whether
  there is a fair way to recognise them. No outcome is promised.
- We planned to raise on MetaDAO's permissionless platform **Backable** (named
  Futardio until 5 October 2026). The raise was removed from the platform. On
  9 November 2026 Backable changed its description from "permissionless" to
  "open" and added platform-level moderation.
- We like MetaDAO's structure:
  - a market-governed ("futarchy") treasury that the team cannot drain;
  - team tokens released only at price milestones;
  - liquidity seeded from the raise;
  - refunds if the raise fails.
- We could not get two things on MetaDAO: a way to look after the legacy
  community, and staking of the original token. A proposal to stake the
  original token for DAO participation was raised publicly (by toly) and
  declined by the platform.

**Starting question:** can we take what MetaDAO built and adjust it, keeping the
safety and governance while adding what we need?

---

## 2. What we want

These are the design goals we are testing ideas against. They are not
commitments.

| # | Design goal |
|---|---|
| R1 | A raise with MetaDAO-grade safety: escrowed funds, a minimum, refunds, one price for everyone |
| R2 | A treasury governed by markets (futarchy), not controlled by the team |
| R3 | Team supply released only at price milestones |
| R4 | A **guaranteed allocation** in the raise for pre-announcement legacy holders |
| R5 | A **legacy-holder tranche** of supply, also released at price milestones |
| R6 | **Staking of the original token** that counts for something real |
| R7 | Redirect the old token's **pump.fun creator fees** from buyback-and-burn to buying the new token and airdropping it to pre-announcement holders |
| R8 | **Trading fees go to us** (the Percolator DAO treasury), not a third party |
| R9 | **No third-party admin control** over our treasury, governance, or raise |
| R10 | **No third-party permission required** to launch |

---

## 3. How the MetaDAO raise system works (v0.8)

Source: `metaDAOproject/programs`, branch `develop`, read at commit `74aec75`
(November 2026). Paths below are relative to that repository.

### 3.1 Programs involved

- **`v08_launchpad`** (mainnet `moonDJUo…`): the raise.
- **`futarchy`** (mainnet `FUTARE…`): DAO, proposals, pass/fail markets, its own
  AMM, and Squads multisig control.
- **`performance_package_v2`** (mainnet `pPV2…`): price-milestone unlocks.
- **`mint_governor`** (mainnet `gvnr…`): delegated mint authority.
- **`bid_wall`**: price floor.
- **`gated_mint`**: transfer restrictions.

**External dependencies:**
- **Squads v4** (treasury multisig)
- **Meteora DAMM v2** (pool)
- **Metaplex** (metadata)
- **USDC**

We confirmed over RPC that all four mainnet programs listed above are deployed
and executable.

### 3.2 Raise lifecycle

| # | Instruction | Caller | Effect |
|---|---|---|---|
| 1 | `initialize_launch` | Anyone; the launch authority is any pubkey | Creates the mint, mints the initial supply into a vault, creates the mint governor |
| 2 | `start_launch` | Launch authority | Opens the raise |
| 3 | `fund` | Anyone | Deposits USDC and creates a per-funder record. No cap and no whitelist |
| 3b | `extend_launch` | **MetaDAO multisig only** | Extends the raise |
| 4 | `close_launch` | Anyone, after the deadline | Moves to Refunding if below the minimum, otherwise Closed |
| 5 | `set_funding_record_approval` | Launch authority, within 2 days | Decides how much of each commitment is accepted. **Allocation is entirely off-chain and discretionary** |
| 6 | `settle_launch` | Authority, or anyone after 2 days | Creates the DAO and Squads treasury, seeds the futarchy AMM and the Meteora pool, sends USDC to the treasury |
| 7 | `finalize_launch` | Anyone | Creates the team performance package and hands mint control to the DAO |
| 8–10 | `claim`, `refund`, `claim_additional_token_allocation` | Anyone | Buyers claim tokens, excess is refunded, the extra allocation is paid out |

### 3.3 Supply and money split (hard-coded constants)

- **Tokens:**
  - **10,000,000** to raise participants. Price = total accepted USDC ÷ 10M.
  - **2,000,000** to the futarchy AMM, paired with **20% of accepted USDC**.
  - **900,000** single-sided into a Meteora pool. A code comment says 3M; the
    code uses 900k.
  - Optional **additional allocation**: one recipient, one fixed amount, minted
    up front.
  - **Team performance package:** minted later, capped. Five tranches at
    **2×, 4×, 8×, 16× and 32×** the launch price, measured by the futarchy TWAP,
    with a minimum unlock delay.
- **USDC:** 80% goes to the treasury, or the excess goes to a bid wall if one is
  configured.

### 3.4 Governance details that matter to us

- **Proposals are decided by markets, not votes.** Pass and fail conditional
  markets run for 3 days, and the TWAP decides.
- **Staking only gates proposals.** `stake_to_proposal` stakes **only the DAO's
  own token**, and only to sponsor a proposal launch. Nothing in the program
  gives voting power from another token.
- **MetaDAO admin powers inside the deployed programs:**
  - **Treasury override.** `admin_enqueue_multisig_proposal_approval`: the
    MetaDAO admin key `6awyHMsh…` can queue approval of a Squads transaction on
    **any** DAO's treasury whenever no proposal is live. We verified this in
    source; we found no timelock.
  - Admin keys can **cancel proposals** and **extend raises**.
  - A hard-coded permissionless account is a member of every DAO's multisig.
- **Fees to MetaDAO:**
  - **0.5%** protocol taker fee on the futarchy AMM, plus arbitrage profit;
  - fees from the DAO-owned Meteora position;
  - a **3%** sell fee on the bid wall.

### 3.5 What it does not have

- No on-chain allocation rules, guarantees, or whitelists for the raise.
- No staking of external tokens.
- No legacy-holder distribution, apart from the single-recipient "additional
  allocation".
- **Note:** `src/allocator.rs` in the launchpad is a heap allocator copied from
  Squads. It has nothing to do with token allocation.

---

## 4. Options we evaluated

### Option A: use MetaDAO's deployed programs through our own frontend

Every MetaDAO program above can be called permissionlessly, so a raise could run
on their contracts without their website.

- **Pros:** almost no smart-contract work, existing audits, identical mechanics.
- **Cons:** fails **R8, R9 and R10 in practice**:
  - MetaDAO keeps admin powers over our treasury (§3.4).
  - Trading and bid-wall fees go to MetaDAO.
  - Running a raise that the platform declined, on its own rails, depends on a
    party that has already said no.
- **Rejected.**

### Option B: fork current MetaDAO code under a license grant

The current code is under the Business Source License (§5), which forbids
production use without MetaDAO's approval.

- **Cons:** fails **R10** by definition.
- **Rejected.**

### Option C: our own stack (current leading direction, not final)

- Fork the **LGPL-licensed** MetaDAO release (`v0.1`, §5) for the futarchy core.
- Write the rest ourselves: the raise, the AMM, milestone packages, and staking.
- Use only infrastructure that is permissionless and that we only *call*, never
  copy: Squads v4, a public AMM pool, and SPL Token.
- **Meets R1–R10.**
- **Costs:** more engineering, and our own audits (§9).

### Option C′: SPL Governance (Realms) instead of futarchy

- **What it is:** Apache-2.0 and already deployed. It supports staking-based
  voting through voter-weight plugins, so original-token staking for votes
  would work out of the box.
- **Downside:** ordinary token voting, without futarchy's market-based
  protection.
- **Status:** kept as a fallback, not chosen.

---

## 5. License analysis

### 5.1 Current MetaDAO code: Business Source License 1.1

- **Allows:** copy, modify, and **non-production** use.
- **Production use requires:** an Additional Use Grant from MetaDAO LLC (made
  via SPL Memo), or a commercial license.
- **When it opens:** each version converts to *LGPL v2.0 or later* on the
  earlier of the Change Date (`4200-06-09`) or **four years after that version's
  first public release**.
  - v0.2 (April 2024) opens in April 2028.
  - v0.8 opens around 2030.
- **Conclusion:** we cannot deploy any modified version of v0.2 or later without
  permission.

### 5.2 Earlier MetaDAO code: LGPL-3.0, which cannot be revoked

From the upstream repository history, verified against GitHub's API:

| Event | Commit | Date |
|---|---|---|
| License set to **LGPL-3.0** | `449030e` | 2023-07-24 |
| Release tag **`v0`** (ships LGPL) | `669ae97` | 2023-11-08 |
| Release tag **`v0.1`** (ships LGPL) | `a9eaaf5` | 2023-12-15 |
| Last commit under LGPL | `1f34927` | 2024-02-17 |
| License switched to **BSL** | `5452889` | 2024-02-17 |
| Release tag `v0.2` (ships BSL) | `26cfd2d` | 2024-04-03 |

**Why the LGPL release is still usable:**
- LGPL-3.0 incorporates GPL-3.0.
- GPL-3.0 §2 says the rights granted *"are irrevocable provided the stated
  conditions are met."*
- Relicensing only affects versions released afterwards.
- The commits were made by MetaDAO's founder in MetaDAO's official repository,
  and two official release tags ship under LGPL.

**Our conclusion:** we may copy, modify, deploy to mainnet, and charge fees with
code from `v0.1` and earlier, without MetaDAO's permission.

**What the LGPL snapshot contains** (about 1,100 lines):
- **`autocrat_v0`:** the futarchy core. DAO, proposals, pass/fail markets,
  decision by TWAP, and the treasury executing the passing instruction.
- **`conditional_vault`:** pass/fail conditional tokens.
- **Dependencies:** OpenBook v2 order books, and `openbook-twap` (LGPL-2.1) for
  TWAP.

It does **not** contain the launchpad, performance packages, mint governor, bid
wall, or the built-in futarchy AMM. Those arrived later under the BSL.

### 5.3 Our obligations and guardrails

1. **Keep notices.** Retain MetaDAO's copyright notice and the LGPL text, and
   mark our modifications.
2. **Publish source.** A Solana program is one compiled binary, so in practice
   we open-source the full source of every program built on LGPL code. That
   fits our goals anyway.
3. **Write everything else independently.** Never copy from v0.2+ code,
   including the current MetaDAO repository. Copyright protects code, not
   mechanisms or ideas (US 17 U.S.C. §102(b)), so implementing the same
   *concepts* ourselves is fine. Keep a clean commit history as a record.
4. **Dependencies:**
   - `openbook-twap`: LGPL-2.1, compatible.
   - OpenBook v2: no clear license on GitHub (`NOASSERTION`). We plan to remove
     it and use our own AMM.
   - Squads v4 crate: **AGPL-3.0**. Compiling it in requires AGPL for the
     combined program, which is acceptable because we open-source everything.
     The alternative is to hand-build the instructions and not link the crate.
   - Jito merkle distributor: GPL-3.0, acceptable if we use it.
5. **Trademarks.** Do not use the MetaDAO, Futardio, or Backable names or logos.
6. **Patents.** Our searches found no MetaDAO patent filings. Futarchy was
   published by Robin Hanson around 2000, which is prior art. *Confidence is
   medium; a dedicated patent search is a cheap follow-up.*

---

## 6. Candidate architecture

This is the design we are currently exploring. It may change or be abandoned.

```
 Pre-announcement legacy holders           New backers
   │  (snapshot → merkle list)                  │
   ▼                                            ▼
 ┌──────────────────── RAISE / ESCROW PROGRAM (ours, audited pre-raise) ────┐
 │  commit USDC · on-chain guaranteed allocation for listed wallets         │
 │  min / max · close · settle · refund (always available on failure/expiry)│
 │  on success: pay fixed audit tranche → auditor; hold rest until launch   │
 └───────────────┬──────────────────────────────────────────────────────────┘
                 │  launch deadline (hard): if missed → refunds open
                 ▼  after post-raise audit passes
 ┌──────────────────── LAUNCH SEQUENCE ────────────────────────────────────────┐
 │  create mint → mint supply split → seed spot pool (X% of USDC + tokens)    │
 │  → treasury USDC into DAO (Squads v4, spending limit for team budget)      │
 │  → open claims → lock programs (immutable or DAO-controlled upgrades)      │
 └───────────────┬────────────────────────────────────────────────────────────┘
                 ▼
 ┌─ FUTARCHY (LGPL v0.1 fork, modernised) ─┐  ┌─ MILESTONE PACKAGES (ours) ──┐
 │  proposals · pass/fail conditional tokens│  │  team tranche   (2×/4×/8×…)  │
 │  own AMM: spot pool liquidity is split   │  │  legacy tranche (2×/4×/8×…)  │
 │  into pass/fail pools during proposals   │  │  oracle = our TWAP           │
 │  TWAP decides · treasury executes        │  │  legacy → merkle claim       │
 │  fees → DAO treasury                      │  └──────────────────────────────┘
 └──────────────────────────────────────────┘
 ┌─ OLD-TOKEN STAKING (ours) ──────────────┐  ┌─ CREATOR-FEE AIRDROPS ───────┐
 │  lock original token → weight for        │  │  pump.fun fees → public      │
 │  legacy tranche + airdrop share, and     │  │  Squads wallet → buy new     │
 │  counts toward proposal sponsorship      │  │  token → merkle claim        │
 └──────────────────────────────────────────┘  └──────────────────────────────┘
```

Intended properties, if this design is built:
- **No third-party admin keys anywhere.** After launch, the programs are either
  immutable or upgradeable only by the DAO.
- **No mint before the audit passes.** Investors' remaining USDC sits in escrow
  until launch. A missed deadline means refunds.
- **Everything is open source** (an LGPL obligation and a trust requirement).

---

## 7. Ideas for legacy holders (not commitments)

> [!IMPORTANT]
> Everything in this section is an **idea under discussion**. None of it is
> promised to anyone. Eligibility rules, amounts, and whether any of it happens
> at all are undecided. A snapshot, list, or claim page will only exist if the
> whole project goes ahead, and even then the design may differ from what is
> written here.

### 7.1 Who might count

- **Idea:** wallets holding the original token **before the disown
  announcement**.
- **Snapshot:** taken at the last slot before the announcement, using archival
  balance data (an indexer, or Dune/Flipside).
- **Excluded addresses:** the PumpSwap pool, the bonding curve, team wallets,
  and known exchange or program accounts.
- **Gaming risk is low:** the slot is historical and already fixed.

### 7.2 Guaranteed allocation in the raise (R4)

- **The mechanism being explored:** each listed wallet could commit up to a cap of N USDC (per wallet, or
  proportional to snapshot balance), and that amount is **guaranteed** to be
  accepted even if the raise is oversubscribed.
- They pay the same price as everyone else.
- **Enforced on-chain** by a merkle proof at commit time, plus a counter that
  settlement must honor.
- **Contrast:** MetaDAO leaves allocation entirely to the launch authority's
  discretion.

### 7.3 Legacy milestone tranche (R5)

- **Idea:** a fixed share of supply would be reserved at launch.
- It would be released at the same price multiples as the team package, using
  the same TWAP oracle.
- Each release would fund a merkle claim. Shares come from the snapshot balance,
  optionally boosted by staking (§7.4).
- **Caveat:** size it against the float. More unlocked supply means more
  potential sell pressure.

### 7.4 Original-token staking (R6)

- In futarchy, **markets decide; there are no votes**, so "staking for votes"
  has to be translated. Because the code is ours, staked original tokens can:
  1. raise a holder's **share of the legacy tranche and fee airdrops**;
  2. **count toward proposal sponsorship**, in place of or alongside the
     new-token stake requirement;
  3. optionally feed **non-binding signal votes**.
- Binding governance influence still comes from trading the decision markets
  with the new token.
- **Open design choice:** staking as *lock*, where holders keep their tokens,
  or *deposit-and-retire*, which could be combined with recovering SOL from the
  old pool. See the earlier migration analysis.

### 7.5 Creator-fee airdrops (R7)

- **Idea:** route pump.fun creator fees into a **public Squads wallet**
  instead of buyback-and-burn. *Not decided; fees currently remain on
  buyback-and-burn.*
- **If a raise ever succeeded:** on a fixed schedule, buy the new token on the
  open market, publish a merkle root, and let eligible holders claim.
- **If a raise did not happen or failed:** any accumulated SOL would need a
  pre-stated fallback, for example resuming buyback-and-burn.
- **No custom program needed:** script + multisig + distributor.

### 7.6 Tax and legal notes

- Airdrops and claims are likely taxable income for recipients in many
  jurisdictions. Disclose this.
- Running a raise plus a token distribution creates securities exposure.
  Counsel is needed before launch. **This is separate from the license
  question, which §5 settles.**

---

## 8. Liquidity and fees

- **Spot liquidity:**
  - **Seeding:** at launch, the raise seeds the pool with **X% of accepted USDC**
    plus newly minted tokens, owned by the DAO. MetaDAO uses 20%.
  - **Sizing reference:** the old PumpSwap pool held about $167K TVL (about
    $83K per side) when last measured, so a 20% seed of even a $1M raise
    (~$200K USDC) is several times deeper.
- **Futarchy market liquidity:**
  - **The problem in v0.1:** order books need market makers.
  - **Our fix:** our own AMM will **split the DAO's spot liquidity into pass and
    fail pools** while a proposal runs, then merge it back. It is the same
    concept MetaDAO later adopted, written independently.
  - **Result:** the raise-seeded pool serves both trading and governance.
- **Fees:**
  - **Pool fees:** trading fees on DAO-owned liquidity go to the **DAO
    treasury**.
  - **Market fees:** our futarchy markets may also charge a fee to the treasury.
  - **Not a founder income stream:** these fees are governed by the DAO. The
    team is paid through a governance-approved budget (Squads spending limit)
    and the milestone package.

---

## 9. Audit strategy and cost

### 9.1 Two stages

1. **Before the raise:** audit the **raise/escrow program only**, because it
   holds investor USDC before anything else exists.
2. **After the raise:** audit futarchy, the AMM, milestone packages, staking,
   and the launch sequence, **folded into the Percolator perps audit**. Part of
   that audit is paid by a fixed, pre-announced **audit tranche** released from
   escrow at settlement.
   - The token is **not minted until this audit passes**.
   - If launch misses its deadline, remaining USDC is refundable.
   - The audit tranche is disclosed as non-refundable.

### 9.2 Keeping the pre-raise audit small

Scope target: **about 400–700 lines of Rust**, roughly one engineer-week.

- Only USDC moves: commit, close, settle, refund, and pay the audit tranche.
- No minting, no CPIs to Squads, AMMs, or governance.
- Guarantees use a merkle proof.
- Refunds can never be blocked.
- Not upgradeable (or authority burned) before the raise opens.

### 9.3 Cost estimate (as of November 2026)

| Basis | Figure |
|---|---|
| Specialist rate | about $1,600–2,800 per engineer-day (≈ $8K–14K per engineer-week) |
| Simple ~500-line Anchor program | about 3.5–5 engineer-days ≈ $5.5K–15K |
| Firm-week pricing (multi-auditor) | about $15K–45K per week |
| **Our estimate** | **$8K–25K; plan on about $10K–15K** |

### 9.4 Ways to reduce up-front cash

- **Areta Solana Audit Subsidy Program.** A $1M pool of firm-sponsored
  discounts; past awards were $5K–50K, or up to about 30% off. The last visible
  cohort closed in March 2026, so check for a new one.
- **Ask the perps auditor** to do the escrow first as an add-on, with part of
  the fee deferred until the raise succeeds.
- **Get 2–3 quotes** for a frozen scope.
- **Open-source before the audit**, and run a small bug bounty afterwards.
- **Realistic out-of-pocket cost:** about $5K–12K.

---

## 10. Risks and open questions

| Risk | Mitigation |
|---|---|
| Raise misses its minimum | Full refunds. Set a conservative minimum and gauge demand privately first |
| Post-raise audit or build overruns | Hard launch deadline, after which refunds open |
| The audit tranche is spent even if launch fails | Disclose up front; keep it fixed and small |
| Futarchy markets are thin | Raise-seeded pool liquidity split into pass/fail pools; consider a market maker |
| Legacy tranche sell pressure | Price-milestone releases; size against float |
| License misstep (copying BSL code) | Base only on `v0.1`; independent implementation; clean history |
| Securities / tax | Counsel before launch; clear disclosures |
| Residual old-token market | Comms; optional SOL recovery from the old pool via deposit-and-retire |

**Open parameters** (decided in the plan, not here):
- Raise minimum and maximum
- LP seed %
- Legacy tranche size
- Guarantee cap formula
- Snapshot slot
- Staking weights
- Launch deadline
- Audit firm and tranche amount
- Milestone multiples

---

## 11. Sources

**Code**
- MetaDAO programs repository: <https://github.com/metaDAOproject/programs>
  - `develop` at `74aec75`: the current BSL code.
  - Tags `v0` and `v0.1`; commits `449030e`, `1f34927` and `5452889`: license
    history.
- `openbook-twap` (LGPL-2.1): <https://github.com/metaDAOproject/openbook-twap>
- Squads v4 (AGPL-3.0): <https://github.com/Squads-Protocol/v4>
- SPL / SPL Governance (Apache-2.0): <https://github.com/solana-labs/solana-program-library>

**Licenses**
- GNU GPL v3 (§2, irrevocability): <https://www.gnu.org/licenses/gpl-3.0.html>
- GNU LGPL v3: <https://www.gnu.org/licenses/lgpl-3.0.html>

**Backable / Futardio**
- [MetaDAO renames Futardio as Backable (Solana Compass)](https://solanacompass.com/news/metadao-renames-futardio-as-backable-its-permissionless-fundraising-platform-on-solana)
- [MetaDAO launches Backable (Crypto Briefing)](https://cryptobriefing.com/metadao-launches-backable-solana-fundraising/)
- [Backable drops "permissionless" for platform moderation (Solana Compass)](https://solanacompass.com/news/metadaos-backable-removes-percolator-raise-and-drops-permissionless-for-platform-moderation)

**Futarchy background**
- [What is Futarchy? Robin Hanson & Proph3t (Solana Compass)](https://solanacompass.com/learn/Lightspeed/the-most-exciting-experiment-in-crypto-futarchy-robin-hanson-proph3t)
- [What the Futarchy?](https://lehranbrothers.substack.com/p/what-the-futarchy)

**Audit pricing and subsidies**
- [Accretion: Solana audit cost 2026](https://accretion.xyz/blog/solana-audit-cost)
- [DEV Community: Solana audit cost by project size](https://dev.to/jakemalarczyk/how-much-does-a-solana-smart-contract-audit-cost-numbers-by-project-size-53ck)
- [Zealynx: audit pricing 2026](https://www.zealynx.io/research/audit-ops/audit-pricing-2026)
- [SolanaFloor: Areta $1M audit subsidy program](https://solanafloor.com/news/certora-and-other-top-security-firms-to-subsidize-audits-for-solana-builders-through-areta-s-1-million-audit-subsidy-program)
- [Superteam Earn: Audit Subsidy Cohort VI](https://superteam.fun/earn/listing/solana-audit-subsidy-program-cohort-vi-applications-by-march-7th-1/)
