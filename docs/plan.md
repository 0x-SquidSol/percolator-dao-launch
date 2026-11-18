# Start-to-finish plan: an independent, futarchy-governed raise (exploratory)

> [!WARNING]
> **Experimental. Not confirmed. Nothing here is a promise.**
>
> This is a *working plan for one possible route*. It is **not** an
> announcement and **not** a commitment to anyone.
>
> - It is **one of several routes** being explored. We may pick another, or
>   none.
> - **Even if every step below is designed, built and audited, it may never be
>   used.**
> - There is **no confirmed** raise, token, sale, airdrop, allocation, claim or
>   distribution to holders of any token, past or present.
> - Every number and rule below is a **working assumption** that may change or
>   be dropped without notice.
> - **Do not buy, hold, sell or keep any token because of this document.**
>
> Any real launch would be announced only through Percolator's official
> channels, with final terms.

- **Status:** draft working plan, November 2026.
- **Companion docs:** background, options and the license analysis are in
  [research.md](research.md). This document assumes the route described there
  as "Option C: our own stack".
- **Not legal, tax or financial advice.**

---

## Contents

1. [How to read this plan](#1-how-to-read-this-plan)
2. [The idea in one page](#2-the-idea-in-one-page)
3. [Working assumptions (decision register)](#3-working-assumptions-decision-register)
4. [Token supply and pricing](#4-token-supply-and-pricing)
5. [The raise](#5-the-raise)
6. [Treasury, allowance and spending rules](#6-treasury-allowance-and-spending-rules)
7. [Governance (futarchy)](#7-governance-futarchy)
8. [Milestone packages: team and legacy tranche](#8-milestone-packages-team-and-legacy-tranche)
9. [Legacy-holder ideas: scoring and lists](#9-legacy-holder-ideas-scoring-and-lists)
10. [Creator-fee airdrop idea (current old-token holders)](#10-creator-fee-airdrop-idea-current-old-token-holders)
11. [Programs to build](#11-programs-to-build)
12. [Phase-by-phase plan](#12-phase-by-phase-plan)
13. [Budget and runway](#13-budget-and-runway)
14. [Security and key management](#14-security-and-key-management)
15. [Legal, licensing and compliance checklist](#15-legal-licensing-and-compliance-checklist)
16. [Communication rules](#16-communication-rules)
17. [Failure paths and contingencies](#17-failure-paths-and-contingencies)
18. [Risks](#18-risks)
19. [Open items](#19-open-items)
20. [Glossary](#20-glossary)

---

## 1. How to read this plan

- **"Working assumption"** means the current best guess for this route. It is
  not a decision to launch anything.
- **"Would"** is used throughout on purpose. Nothing here *will* happen unless
  separately and officially announced.
- Dollar figures are **USDC** and **estimates** unless stated otherwise.
- "Old token" means the earlier pump.fun token. "New token" means a
  hypothetical token that this route *would* create. "Legacy holders" means
  wallets in the snapshots described in [section 9](#9-legacy-holder-ideas-scoring-and-lists).
- Section numbers are referenced from the [phase plan](#12-phase-by-phase-plan),
  which is the actual start-to-finish checklist.

---

## 2. The idea in one page

If this route were ever used, it would look roughly like this:

1. **Own programs, no third-party control.** Raise/escrow, futarchy, AMM,
   milestone packages and a treasury allowance rule. All open source, with no
   outside admin keys, and upgradeable only through DAO governance with a
   7-day delay.
2. **Everything built first.** All programs would be written and tested before
   a raise. Only the raise/escrow program would be audited before the raise
   (paid by the founders). The rest would be audited after a successful raise,
   paid from the raise, **before any token is created**.
3. **A 7-day raise** in USDC, **$250K minimum, $750K maximum**. Buyers would
   share a fixed **10 million tokens**, so everyone pays the same price
   (amount raised ÷ 10M).
4. **Refunds if it fails.** If the minimum isn't met, or the token isn't
   launched within **3 months** of the raise closing, money would be
   refundable automatically.
5. **Legacy-holder ideas:** up to **50%** of the raise reserved as guaranteed
   spots for snapshot holders, plus an **8%** supply tranche released only at
   price milestones. Both are sized by a published scoring formula.
6. **Team:** **40%** of supply, released only at **2×, 4×, 8×, 16× and 32×**
   the raise price, each held on a 3-month average, and nothing before
   **12 months**.
7. **Treasury:** controlled by futarchy (pass/fail markets). The team gets a
   **monthly allowance** with a "savings bank". A built-in rule pays an
   **external perps audit** automatically once the treasury can afford it.
8. **Liquidity:** **20%** of the raise seeded into a DAO-owned pool. Trading
   fees go to the treasury.
9. **Separately, and only if current old-token holders vote for it:** pump.fun
   creator fees could buy the new token on the market for **weekly** airdrops
   to current old-token holders.

---

## 3. Working assumptions (decision register)

Every item is a working assumption, recorded so the design is consistent. Any
of them can change.

| # | Topic | Working assumption |
|---|---|---|
| 1 | Governance model | Futarchy, with SPL Governance (Realms) as a fallback if futarchy proves impractical |
| 2 | Legacy ideas kept | Guaranteed spot in the raise; milestone tranche; creator-fee airdrops (only if voted). **Staking the old token dropped** |
| 3 | Supply split | Buyers 40%, team 40%, legacy tranche 8%, liquidity 12% |
| 4 | Guaranteed spots | Up to **50%** of the raise; personal amounts from the legacy score, with a small minimum per qualifying wallet |
| 5 | Raise minimum and perps audit | **$250K** minimum. The perps audit is decoupled from launch and paid by an automatic treasury rule (#16) |
| 6 | Raise maximum | **$750K** |
| 7 | Team lock | Nothing released before **12 months**. Then milestones, each with a 3-month average |
| 8 | Allowance | Tiered **$30K / $32.5K / $35K** per month, plus a savings bank (draw up to **+20%** a month from savings, no cap on savings) |
| 9 | Liquidity | **20%** of the raise into the DAO-owned pool |
| 10 | Over-subscription | Guarantees first, then **pro-rata** for everything else. Automatic, no team discretion |
| 11 | Raise length | **7 days**. Guaranteed-amount list and checker page published beforehand |
| 12 | Build order | **Everything built before the raise.** Only the DAO audit happens after |
| 13 | Launch deadline | **3 months** after the raise closes, else refunds |
| 14 | Upgrades | Only through DAO governance, with a **7-day** delay |
| 15 | Governance settings | Same values as MetaDAO's current settings (3-day proposals, 1-day warm-up, +3% pass threshold, −3% for team proposals, 1.5M-token proposal stake). The logic would be written independently |
| 16 | Auto-audit rule | Up to **$300K**, only if **4 months** of allowance remains afterwards, paid **directly to a firm on a published list**, in **up to 2 payments**, no vote needed |
| 17 | Snapshots | Use the existing **pre-crash** snapshot. A second **pre-announcement** snapshot to be taken |
| 18 | Combining snapshots | Credit **each drop separately** (crash drop, announcement drop) |
| 19 | Loyalty boost | 0.25× (<1 wk), 1× (1 wk–1 mo), 1.5× (1–3 mo), 2× (3–6 mo), 2.5× (6–12 mo), 3× (12+ mo). Dip buyers get a flat 1× for the announcement drop |
| 20 | Fairness | **Minimum only** (no maximum). Minimums take ≤ ~20% of the tranche. Exact numbers set after reviewing the data |
| 21 | Exchange holders | If exchange wallets held it: ask the exchange first, then capped self-proof claims. Otherwise skip |
| 22 | Creator-fee airdrops | Only if voted. Public wallet, buys spread out, **weekly** drops by average holding, 90-day claim then roll forward, never to the team |
| 23 | Price floor (bid wall) | **None at launch.** The DAO can vote on buybacks later |
| 24 | Dispute window | **1 week** on the published legacy list, then locked |
| 25 | Pricing | Fixed 10M buyer tokens; **price = amount raised ÷ 10M** |
| 26 | Allowance recipients | Both founders' wallets on the allowance list, drawing from **one shared monthly pot** |
| 27 | Cost disclosure | Public docs show allowance totals only. Breakdown kept in a git-ignored private file |
| 28 | Deposits during the raise | Locked until close, like MetaDAO. Refunds only after close |
| 29 | Where code lives | In this public repository, from the start, clearly marked experimental and unaudited |
| 30 | Raise program upgrades | **None.** The raise/escrow program would be made immutable once its audited version is deployed |
| 31 | Check window before launch | DAO programs deployed → **7-day public check window** → launch. No withdrawals during it. Depositors are responsible for verifying programs and are told how |
| 32 | Team proposal shortcut | Exactly as MetaDAO: team-sponsored proposals need no stake and pass unless fail beats pass by more than 3%, on any proposal type |
| 33 | Who starts milestone checks | As MetaDAO: the team starts its own 3-month checks, only after the 12-month lock; anyone can start checks for the legacy tranche. Checks always measure the next 3 months |
| 34 | Minimum deposit | $10 per deposit |
| 35 | Extra review of the raise program | Audit plus a public bug bounty of up to $10–25K, run for 2–4 weeks on devnet **before** the raise program is deployed to mainnet (where it can't be changed) |
| 36 | Team wallets in the legacy list | Excluded and kept private. Published: how many, their total holdings, and a fingerprint, privately confirmed by an independent checker. The public script reproduces every other wallet's result exactly |

---

## 4. Token supply and pricing

### 4.1 Supply

Total maximum supply: **25,000,000** tokens. That figure is a working
assumption and follows from 10M = 40%.

| Group | Share | Tokens | When it exists |
|---|---|---|---|
| Raise buyers | 40% | 10,000,000 | Created at launch |
| Liquidity | 12% | 3,000,000 | Created at launch (see 4.3) |
| Team package | 40% | 10,000,000 | Created only as milestones are met (2M per milestone) |
| Legacy tranche | 8% | 2,000,000 | Created only as milestones are met (400K per milestone) |

- On launch day, only buyers' and liquidity tokens would exist (13M).
- No other minting would be possible except through rules fixed at launch.
  Whether the DAO could ever mint more is an [open item](#19-open-items).

### 4.2 Price

- **Price = total accepted raise ÷ 10,000,000**, the same for everyone.

| Accepted raise | Price | Fully diluted value (25M) | Launch-day value (13M) |
|---|---|---|---|
| $250K | $0.025 | ~$625K | ~$325K |
| $500K | $0.050 | ~$1.25M | ~$650K |
| $750K | $0.075 | ~$1.875M | ~$975K |

### 4.3 Liquidity tokens

- **2,000,000** tokens would be paired with **20% of the raise** at exactly
  the raise price. This mirrors MetaDAO's 2M-token futarchy pool.
- The remaining **~1,000,000** (4%) would be a **DAO liquidity reserve**, held
  by the treasury for future liquidity (MetaDAO puts its equivalent 900K into a
  second, one-sided pool). Exact use is an [open item](#19-open-items).

### 4.4 Milestone prices

Milestones are multiples of the final raise price:

| Milestone | Multiple | At $250K raise | At $750K raise | Team release | Legacy release |
|---|---|---|---|---|---|
| 1 | 2× | $0.05 | $0.15 | 2M | 400K |
| 2 | 4× | $0.10 | $0.30 | 2M | 400K |
| 3 | 8× | $0.20 | $0.60 | 2M | 400K |
| 4 | 16× | $0.40 | $1.20 | 2M | 400K |
| 5 | 32× | $0.80 | $2.40 | 2M | 400K |

---

## 5. The raise

### 5.1 Parameters

| Parameter | Working assumption |
|---|---|
| Currency | USDC |
| Minimum | $250,000 |
| Maximum accepted | $750,000 (more can be offered; the excess is refunded) |
| Length | 7 days |
| Tokens to buyers | 10,000,000, shared by accepted amount |
| Guaranteed reserve | Up to 50% of the maximum ($375K) for snapshot holders |
| Launch deadline | 3 months after close |

### 5.2 Before it opens

1. Publish the final legacy list (after the 1-week dispute window, section 9.7)
   with each wallet's **guaranteed amount**.
2. Commit the list to the raise program as a **merkle root** (a single
   fingerprint of the whole list), so nobody can change it later.
3. Launch a **checker page**: paste a wallet, see the guaranteed amount and how
   it was calculated.
4. Publish the raise terms, program addresses, audit report and
   verifiable-build hashes.
5. Publish the list, checker page and opening time **at least a week
   ahead**, so legacy holders have time to check their amount and prepare
   USDC.

### 5.3 During the 7 days

- Anyone can deposit USDC, **minimum $10 per deposit**. Snapshot wallets
  deposit with a proof of their guaranteed amount.
- Deposits **cannot be withdrawn while the raise is open**, the same as
  MetaDAO. This stops last-minute pull-outs from moving the total or the
  price. Refunds happen only after close (section 5.4).
- Running totals are public on-chain and shown on the page.

### 5.4 Closing and allocation

When the 7 days end, anyone can trigger the close:

1. **Minimum not met** → the raise fails. Everyone can withdraw 100%.
2. **Minimum met, ≤ $750K offered** → everything is accepted.
3. **More than $750K offered** →
   1. guaranteed amounts accepted first (each wallet up to its own
      guarantee, total ≤ $375K);
   2. everything else is accepted **pro-rata** to fill the remaining space;
   3. the rest is refunded.

Unused guaranteed space flows back to everyone else automatically.

### 5.5 Between close and launch (≤ 3 months)

- Accepted funds stay in the escrow program. **The team cannot take them.**
- Only one payment can leave before launch: the **DAO audit fee**, paid
  straight to the audit firm. It has a fixed cap stated in the raise terms, and
  that cap is an [open item](#19-open-items) pending quotes.
- After the audited DAO programs are deployed, there would be a **7-day
  public check window** before launch, so anyone can compare the deployed
  programs with the audited builds. Deposits still can't be withdrawn during
  it. The window has to fit inside the 3-month deadline.
- If the token isn't launched within 3 months, anyone can trigger
  **refund mode**. Buyers get back their accepted amount minus their pro-rata
  share of the audit fee already paid. This must be stated clearly before the
  raise.

### 5.6 Launch (settlement)

One permissionless sequence, which anyone could trigger once the check
window has passed. The raise program would refuse to start it unless every
DAO program's upgrade authority is already the DAO's 7-day upgrade multisig.
Once settlement starts, refund mode can't start, and vice versa.

1. Create the token and mint 13M (10M buyers + 3M liquidity).
2. Create the DAO and treasury (section 6), with the allowance tier set from
   the accepted total.
3. Seed the pool: 20% of the raise + 2M tokens at the raise price.
4. Move the remaining USDC to the treasury.
5. Create the team and legacy milestone packages (section 8).
6. Hand the mint authority to the milestone program, which holds hard-coded
   caps, and the upgrade authorities to the DAO with the 7-day delay.
7. Buyers claim their tokens; refunds of any excess are claimable.

---

## 6. Treasury, allowance and spending rules

### 6.1 Treasury

- A **Squads v4** multisig vault, controlled by the DAO program. We would call
  Squads, not copy it.
- A public **execute-only** member lets anyone carry out a transaction the DAO
  has already approved. It can't approve or change anything.
- Whether the Squads v4 program itself can be upgraded by a third party is
  being checked. The result would be disclosed.
- **No third-party admin key** and no team key on the treasury.

### 6.2 Monthly allowance

| Accepted raise | Monthly allowance |
|---|---|
| $250K – $499,999 | $30,000 |
| $500K – $749,999 | $32,500 |
| $750K | $35,000 |

- Set once at launch from the accepted total. Changing it requires a
  governance proposal.
- **Recipients:** both founders' wallets, drawing from **one shared monthly
  pot**. Either can draw any part of it.
- **Safety check** (copied from MetaDAO): the minimum raise must cover at
  least 6 months of allowance. $250K ≥ 6 × $30K = $180K. ✔
- What the allowance covers in total (salaries, infrastructure, travel,
  contributors) is public. The breakdown is kept private.

### 6.3 Savings bank

- Unspent allowance is credited to a **savings balance**. The money itself
  stays in the treasury.
- In any month, the team may draw **allowance + up to 20% of the allowance**,
  but only the part covered by savings. The most in any one month is
  **1.2× the allowance**.
- No cap on the savings balance. The 20% limit already prevents lump sums.
- Over time, the team can never draw more than the allowance on average.
- Squads' built-in spending limit can't do this, so it would be a **small
  custom program** (section 11).

**Example at $30K:** spend $25K, $25K, $25K (savings $15K), then $36K for a
trip month ($6K from savings, leaving $9K).

### 6.4 Automatic perps-audit rule

Written into the launch terms, so **no holder vote is needed**:

- Pays up to **$300K** in total.
- Only if the treasury still holds **≥ 4 months of allowance** after the
  payment.
- Only **directly to an audit firm on a published list**, fixed at launch
  (e.g. OtterSec, Neodyme, Zellic, Accretion, Ackee, Sec3, or similar). A firm
  not on the list would need a proposal.
- In **up to 2 payments** (deposit and final).
- The team triggers it with the firm's invoice and address, and everything is
  public on-chain. The reserve check is enforced by the program.

### 6.5 Everything else

Any other spending (marketing pushes, hires, buybacks, allowance changes,
grants) requires a **futarchy proposal**.

### 6.6 No price floor

There would be no bid wall at launch. Buybacks remain possible later through a
normal proposal.

---

## 7. Governance (futarchy)

### 7.1 How a decision would be made

1. Someone posts a proposal. Non-team proposers lock 1.5M tokens while it runs.
2. For 3 days, two markets trade: "the token if this passes" and "the token if
   this fails".
3. The first day is a warm-up that doesn't count toward the averages.
4. If the **pass** average beats **fail** by more than **3%**, it passes. Team
   proposals pass unless **fail** beats **pass** by more than 3%.
5. A passed proposal executes its transaction from the treasury.

### 7.2 Settings

| Setting | Value |
|---|---|
| Proposal length | 3 days |
| Warm-up (excluded from averages) | 1 day |
| Pass threshold | +3% |
| Team-proposal threshold | −3% |
| Proposal stake (non-team) | 1,500,000 tokens |

These values match MetaDAO's current settings. Numbers aren't protected by
copyright, but the **code** implementing them would be written independently
or forked only from the LGPL-era release ([research.md §5](research.md)).

### 7.3 Liquidity during proposals

Our AMM would split the spot pool into pass and fail pools while a proposal
runs, then merge it back. That way governance markets have real depth without
separate liquidity.

### 7.4 Upgrades

- Program upgrade authority is held by a separate, **self-governing** upgrade
  multisig whose only voter is the DAO. Nobody can change its settings
  directly, so even changing the delay itself takes 7 days.
- Upgrades go through a normal proposal, then a **7-day delay** before taking
  effect, so anyone who disagrees can exit first.
- The raise/escrow program is the exception: it would have **no upgrade
  authority at all** once its audited version is deployed.

### 7.5 Fallback

If futarchy proves impractical (cost, audit findings, thin markets), the
fallback is **SPL Governance (Realms)** voting with the new token. That would
need a revised plan.

---

## 8. Milestone packages: team and legacy tranche

### 8.1 Shared mechanics

- Five milestones at **2×, 4×, 8×, 16×, 32×** the raise price, each releasing
  20% of the package.
- A milestone counts only when the **average price over 3 months** is at or
  above it. A single spike doesn't count.
- The average comes from the DAO pool's price oracle, which limits how fast
  each observation can move to resist manipulation.
- Several milestones can be released together if the average clears them.
- **Who starts a check** (as MetaDAO): the team starts checks for its own
  package, only after its 12-month lock; anyone can start checks for the
  legacy tranche. A check always measures the *next* 3 months, so nobody can
  pick a good period that has already happened.
- Tokens are **created at release**, not before.

### 8.2 Team package (40%)

- Nothing released before **12 months** after launch.
- After that, each milestone releases once its 3-month condition is met.
- Released to a team address fixed at launch, which can be changed only by
  proposal.

### 8.3 Legacy tranche (8%) (an idea, not a commitment)

- **No extra lock** beyond the 3-month average, so the earliest possible
  release is about 3 months after launch.
- Whether milestones ever expire (for this package or the team's) is an
  [open item](#19-open-items).
- Each release is shared by the legacy scores (section 9) and claimed through
  a claim page using the published list.
- What happens to tranche tokens nobody claims is an
  [open item](#19-open-items).

---

## 9. Legacy-holder ideas: scoring and lists

> [!IMPORTANT]
> Everything in this section is an **idea under exploration**. No holder of
> any token is promised a spot, tranche, airdrop or anything else.

### 9.1 Snapshots

| Snapshot | Moment | Status |
|---|---|---|
| S1 | Just before the crash | Already taken |
| S2 | Just before the announcement (~6 hours after the crash) | To be taken from chain history |

### 9.2 What counts as holding

- Tokens in the wallet itself.
- The holder's share of tokens inside **liquidity pools they owned a position
  in**. The main pump.fun pool doesn't count, since its liquidity is locked
  and nobody personally owns it.
- **Exchange balances**, only if the data shows exchanges held the token: ask
  each exchange first, then allow capped self-proof claims during the dispute
  window.

### 9.3 Exclusions

- Team-linked wallets. These would stay private; what's published is how
  many were excluded, their total holdings, and a fingerprint of the list,
  privately confirmed by an independent checker. The public script still
  reproduces every other wallet's result exactly.
- Pools, program accounts and bonding-curve accounts.
- Bots, snipers and bundlers (rules to be published, e.g. bought and sold
  within minutes, or clusters funded from one source).
- Dust wallets below the qualifying amount.

### 9.4 Score

Each drop is credited separately:

```
crash credit         = held at S1 × crash drop %
announcement credit  = held at S2 × announcement drop %
score                = (crash credit + announcement credit) × loyalty boost
```

- **Held through both drops:** credit for both, with their loyalty boost
  applied.
- **Sold during the crash:** crash credit only, with the boost.
- **Bought the dip** (tokens bought between S1 and S2): announcement credit
  only, at a **flat 1×**, since that window was only about 6 hours. If a
  pre-crash holder also bought the dip, the extra tokens count at 1×.

Loyalty boost, based on the **average amount held over time before the
crash**:

| Held for | Boost |
|---|---|
| Under 1 week | 0.25× |
| 1 week – 1 month | 1× |
| 1 – 3 months | 1.5× |
| 3 – 6 months | 2× |
| 6 – 12 months | 2.5× |
| 12+ months | 3× |
| Dip buyers (bought between S1 and S2) | Flat 1× on the announcement drop |

### 9.5 Turning scores into amounts

- **Tranche share** = score ÷ total scores, after minimums.
- **Minimum only, no maximum.** Every qualifying wallet gets at least a
  minimum, and minimums take no more than ~20% of the tranche.
- **Guaranteed raise spot** = the same score, scaled so the total equals $375K,
  with a small per-wallet minimum (e.g. ~$100).
- Exact minimums and the qualifying amount are set **after** the data is
  reviewed.

### 9.6 Data pipeline

1. Load S1. Pull S2 and full transfer history for every wallet from an archive
   RPC or indexer.
2. Rebuild each wallet's balance over time, including LP positions.
3. Label exchange, pool, program and team wallets. Run the bot/sniper rules.
4. Compute scores, minimums, tranche shares and guaranteed amounts.
5. Output the full list as CSV, the merkle root and a methodology note.
6. Make the **script public**, so anyone can reproduce the list from chain
   data.

### 9.7 Publication and disputes

1. Publish the draft list, script and methodology.
2. **1-week dispute window**: missed wallets, wallets wrongly excluded,
   own-wallet transfers, exchange self-proof claims (capped).
3. Publish the decisions on disputes and the final list.
4. **Lock**: the final merkle root goes into the raise and tranche programs.
   After that nobody, team included, can change it.

### 9.8 Tax note

Receiving tokens may be taxable in many places. Any final terms would say so.

---

## 10. Creator-fee airdrop idea (current old-token holders)

> [!IMPORTANT]
> An idea only. It would happen **only if current old-token holders vote for
> it**, and only if a new token ever exists.

1. **Vote first** on the existing voting page: keep buyback-and-burn, or
   switch to "buy the new token and airdrop it".
2. **If switched:** creator fees collect in a **public wallet** from the moment
   the vote passes.
3. **If no new token ever launches** (the raise fails or the deadline is
   missed), the collected funds go back to **buyback-and-burn**.
4. **After launch:** fees buy the new token in **small amounts spread over
   time**.
5. **Weekly drops** to people holding the old token, weighted by their
   **average holding over that week**, with a small qualifying minimum.
6. **Claim page.** Shares accumulate, so a holder can claim many weeks at once
   and pay one fee. Each week's share is claimable for **90 days**, then rolls
   into the next drop. It **never goes to the team**.
7. **Tooling:** a script + public wallet + an existing open-source merkle
   distributor (license checked). No new program needed.

---

## 11. Programs to build

| # | Program | Source | Audit stage |
|---|---|---|---|
| P1 | **Raise/escrow**: deposits, guaranteed amounts (merkle), close, pro-rata, refunds, audit-fee payout, launch deadline, settlement hand-off | Written independently | **Pre-raise** |
| P2 | **Futarchy**: proposals, pass/fail resolution, treasury execution, upgrade-delay handling | Forked from MetaDAO's LGPL `v0.1` (autocrat + conditional vault), modernized | Post-raise |
| P3 | **AMM + oracle**: spot pool, split/merge into pass/fail pools, fee to treasury, manipulation-resistant average price | Written independently (LGPL-era AMM code may be referenced) | Post-raise |
| P4 | **Milestone packages**: team and legacy packages, 3-month average checks, 12-month team lock, capped minting | Written independently | Post-raise |
| P5 | **Allowance/savings bank + auto-audit rule** | Written independently | Post-raise |
| P6 | **Claims**: legacy tranche claims (merkle). May reuse an open-source distributor | Existing open source, license checked | Post-raise |

Shared rules for all programs:

- Never copy MetaDAO code from after the BSL switch. Keep a provenance log
  for every file.
- Squads v4 via CPI only. Design around the runtime rule that a program can't
  appear twice in one CPI stack (validate in one transaction, execute in
  another).
- Verifiable builds. Public source. Full test suites (unit + integration +
  end-to-end lifecycle).
- Events for every state change, for indexers and the frontend.

Off-chain pieces: raise frontend, checker page, claim pages, proposal/trading
UI, legacy scoring script, creator-fee airdrop script, monitoring/alerts.

---

## 12. Phase-by-phase plan

Durations are rough estimates. Phases can overlap where noted. **Every phase
ends with a go/no-go**: stopping at any point is a valid outcome.

### Phase 0: Groundwork and go/no-go

- [ ] Confirm this route is worth pursuing versus the other routes.
- [ ] Legal: speak to securities and tax counsel (section 15). Decide whether
  a legal entity/foundation is needed and in which jurisdiction.
- [ ] Get counsel's view on the license analysis (LGPL fork, Squads AGPL).
- [ ] Pick a license for this repo's code.
- [ ] Request quotes from 3+ audit firms for P1 (pre-raise) and P2–P6
  (post-raise). Apply to audit-subsidy programs.
- [ ] Set up a private cost file (git-ignored) and a budget for pre-raise costs.

*Exit:* legal green light to continue designing; audit quotes in hand.

### Phase 1: Legacy data (can run alongside Phases 2–3)

- [ ] Take snapshot S2 (pre-announcement).
- [ ] Build the scoring pipeline (section 9.6).
- [ ] Check whether exchanges held the old token. If yes, contact them.
- [ ] Review the distribution. Set the qualifying amount and minimums.
- [ ] Prepare the draft list, methodology and public script (not yet
  published).

*Exit:* a reproducible draft list that internal review agrees is fair.

### Phase 2: Specifications

- [ ] Write a spec for each program P1–P6: accounts, instructions, rules,
  invariants, failure cases.
- [ ] Write the launch-sequence spec (section 5.6) and an end-to-end state
  diagram.
- [ ] Finalize the open items that affect code (section 19).
- [ ] Threat model: price manipulation of averages, griefing proposals, key
  loss, deadline edge cases, rounding in pro-rata.

*Exit:* specs reviewed. Auditor pre-read of the P1 spec if possible.

### Phase 3: Build (est. several months)

- [ ] Fork LGPL `v0.1`. Record the provenance. Upgrade toolchains.
- [ ] Build P1 first (it's on the critical path for the pre-raise audit).
- [ ] Build P3 → P2 → P4 → P5 → P6.
- [ ] Tests: unit, integration and full lifecycle (success path, fail path,
  deadline-refund path, over-subscription path).
- [ ] Frontends: raise, checker, claims, governance.
- [ ] Devnet deployment of the whole stack.

*Exit:* all programs feature-complete with passing test suites.

### Phase 4: Pre-raise audit (P1 only)

- [ ] Freeze P1. Send it to the chosen firm.
- [ ] Fix findings. Get the re-review. Publish the report.
- [ ] **Book the post-raise audit slot** for P2–P6 to start right after the
  raise closes.
- [ ] Optional upgrade: if a subsidy or deferred payment allows it, audit
  P2–P6 before the raise too, so launch can follow within days.

- [ ] Run a public **bug bounty** on the audited raise program for 2–4 weeks
  on devnet, **before** any mainnet deployment. Fix and re-review any valid
  report.

*Exit:* clean P1 audit report published; bounty period complete.

### Phase 5: Rehearsal

- [ ] Full dress rehearsal on devnet: test raise, close, over-subscription,
  launch, proposals, milestone simulation, allowance and savings bank,
  auto-audit rule, refund mode.
- [ ] Public devnet test so the community can try deposits and the checker
  page with fake funds.
- [ ] Deploy P1 to mainnet with a verifiable build, then remove its upgrade
  authority (immutable).

*Exit:* rehearsal passes with no blocking issues.

### Phase 6: Community steps

- [ ] Publish the draft legacy list, script and methodology.
- [ ] Run the **1-week dispute window**. Resolve disputes. Publish the final
  list and lock the merkle root.
- [ ] If pursuing the creator-fee idea: run the **old-token vote**. If it
  passes, set up the public fee wallet.
- [ ] Publish the full raise terms, risks, the audit report and program
  addresses.

*Exit:* final list locked; terms published; counsel sign-off on the terms.

### Phase 7: The raise (7 days)

- [ ] Announce the opening time in advance on official channels only.
- [ ] Open the raise. Monitor deposits and the frontend.
- [ ] Close and trigger allocation.
- [ ] **If the minimum is missed:** refunds open; the creator-fee funds go back
  to buyback-and-burn; post-mortem.

*Exit:* raise succeeded or refunds are open.

### Phase 8: Post-raise audit and fixes (≤ 3 months)

- [ ] The audit fee is paid from escrow to the firm (within the cap).
- [ ] Audit P2–P6. Fix and re-review. Publish the report.
- [ ] Final mainnet deployment of P2–P6 with verifiable builds, upgrade
  authority set to the DAO's upgrade multisig.
- [ ] Publish build fingerprints. **7-day public check window** before
  launch.
- [ ] Weekly public status updates while funds sit in escrow.
- [ ] **If the 3-month deadline approaches with no launch:** refund mode.

*Exit:* audited programs on mainnet.

### Phase 9: Launch day

- [ ] Run the settlement sequence (section 5.6).
- [ ] Verify on-chain: supply, pool, treasury balance, allowance tier,
  packages, authorities handed to the DAO.
- [ ] Open buyer claims and refund claims.
- [ ] Publish all addresses and a launch report.

### Phase 10: Operations after launch

- [ ] **Allowance:** monthly draws, with public monthly spending notes.
- [ ] **Auto-audit rule:** trigger when the treasury meets the reserve test.
- [ ] **Proposals:** operate the governance UI; document how anyone can
  propose.
- [ ] **Milestones:** monitor averages and open legacy claims at each release.
- [ ] **Creator-fee drops** (if voted): weekly buys, drops, 90-day roll-forward.
- [ ] **Monitoring:** alerts on treasury movements, oracle anomalies,
  proposal activity.
- [ ] **Bug bounty** program.
- [ ] Quarterly public treasury report.

---

## 13. Budget and runway

### 13.1 Costs before any raise (paid by the founders)

| Item | Estimate |
|---|---|
| P1 pre-raise audit | ~$10–15K (range $8–25K); subsidies may reduce it |
| P1 bug bounty | Up to $10–25K, **paid only if a valid serious bug is found** |
| Legal (initial counsel) | To be quoted |
| Data (archive RPC/indexer for the snapshot pipeline) | Low hundreds to low thousands |
| Devnet/mainnet deployment rent and fees | Low thousands |

### 13.2 Paid from the raise

| Item | Estimate |
|---|---|
| Liquidity (20%) | $50K / $100K / $150K at $250K / $500K / $750K |
| DAO audit (P2–P6) | ~$25–100K, **quotes needed** |
| Perps audit | Via the auto-audit rule, up to $300K (an estimated $150K with discount) |

### 13.3 Runway (allowance fully drawn, after liquidity and a $25K DAO audit)

| Raise | Left to run on | Allowance | Runway | Perps audit from raise money? |
|---|---|---|---|---|
| $250K | ~$175K | $30K | ~5.8 months | Not without a discount, subsidy or other income |
| $500K | ~$375K | $32.5K | ~11.5 months (~7 after a $150K audit) | Yes, right away at $150K |
| $750K | ~$575K | $35K | ~16.4 months (~12 after a $150K audit) | Yes, right away at $150K |

The allowance is a ceiling. Spending less extends runway.

---

## 14. Security and key management

- **No upgrade keys held by the team after launch.** Upgrade authority goes to
  the DAO with a 7-day delay.
- **The raise/escrow program is immutable** once its audited version is
  deployed, so nobody can change it while it holds deposits.
- **DAO programs** would be deployed with their upgrade authority already set
  to the DAO's 7-day upgrade multisig, checked by the raise program before
  launch, followed by a 7-day public check window.
- **Before that**, deploy keys are held in a founder multisig on hardware
  wallets, under a written key-handling procedure.
- **Founders' allowance wallets** on hardware wallets. A lost wallet can be
  replaced only by a proposal (the other founder can still draw from the
  shared pot meanwhile).
- **Oracle safety:** the average price has a per-update change limit, plus a
  deep pool (20%) to make manipulation expensive.
- **Audits:** P1 before the raise; P2–P6 after; perps separately.
- **Bug bounty** after launch.
- **Incident plan:** who to contact, how to pause frontends, how an emergency
  fix goes through governance (and how long that takes).

---

## 15. Legal, licensing and compliance checklist

- [ ] Securities analysis of the raise and of the legacy ideas, by
  jurisdiction.
- [ ] Whether to restrict participation by jurisdiction (e.g. geo-blocking,
  attestations), and sanctions screening.
- [ ] Legal wrapper (foundation or company) to hold IP, contracts and
  liabilities.
- [ ] Tax treatment: raise proceeds, treasury, allowance, airdrops and
  claims.
- [ ] Terms of use and a risk disclosure for the raise, claims and governance.
- [ ] License compliance: LGPL fork obligations (keep notices, publish
  modified source), Squads AGPL implications, distributor license, BSL
  avoidance with a provenance log.
- [ ] Trademark care: no use of MetaDAO/Futardio/Backable branding.
- [ ] Privacy: no personal data in public repos.

---

## 16. Communication rules

- Every public doc keeps the **experimental / no promises** banner.
- Use "idea", "exploring", "working assumption". Never "will", "guaranteed",
  "confirmed" for any outcome.
- Nothing is announced outside official channels. No dates until terms are
  final.
- Never encourage anyone to buy, hold or sell any token.
- Any raise terms would carry a prominent **"verify before you deposit"**
  warning: deposits can't be withdrawn, and here is how to check the programs.
- Private notes (costs, negotiations) stay in git-ignored `*.private.md`
  files.

---

## 17. Failure paths and contingencies

| What goes wrong | What would happen |
|---|---|
| Route abandoned at any phase | Nothing launches. Docs stay as a record. Nobody is owed anything |
| P1 audit finds serious issues | Fix and re-audit before any raise; delay the raise |
| Legal advice against | Redesign or stop |
| Raise misses $250K | Full refunds. Creator-fee funds go back to buyback-and-burn |
| DAO audit is late or fails | Fix within the 3 months; otherwise refund mode (minus the audit fee share) |
| Creator-fee vote fails | Buyback-and-burn continues. No airdrops |
| Futarchy markets too thin | Proposal to adjust settings, or move to the Realms fallback |
| Perps audit unaffordable | Rule waits for funds; seek subsidies, discounts or a proposal for other funding |
| A founder's wallet is lost | The other founder draws from the shared pot; a proposal replaces the address |
| Bug after launch | Fix through a proposal + 7-day delay |

---

## 18. Risks

- **Execution:** building and auditing six programs is a lot of work before
  any money comes in.
- **Thin markets:** a small raise means a small pool. Averages and governance
  markets could be easier to push.
- **High proposal stake:** 1.5M tokens is ~11.5% of the 13M tokens that
  exist at launch, so outside proposals may be rare early on. That's the same
  as MetaDAO, and it can be changed by proposal.
- **Runway:** at the $250K minimum, runway is under 6 months with the perps
  audit unfunded.
- **Legal and regulatory:** unresolved until counsel reviews.
- **Community expectations:** people may read ideas as promises. Mitigated by
  the communication rules.
- **Data accuracy:** errors in the legacy list. Mitigated by a public script
  and the dispute window, but 1 week is short.
- **License:** relies on the LGPL analysis. Counsel to confirm.
- **Immutable raise program:** once deployed it can't be patched, which is
  why it gets an audit, a bug bounty and rehearsals first. The refund paths
  are the safety valve.
- **USDC issuer controls:** USDC's issuer can freeze USDC accounts, including
  an escrow vault. This is outside the project's control.
- **Team proposal shortcut:** as on MetaDAO, team proposals pass unless the
  market clearly objects, including on proposals that benefit the team.

---

## 19. Open items

Items to settle later, with the user's input:

1. DAO audit fee cap payable from escrow (needs quotes).
2. Use of the ~1M-token DAO liquidity reserve.
3. Whether the DAO can ever mint beyond 25M.
4. Unclaimed legacy-tranche tokens: claim period and where they go.
5. Whether milestones expire (team package and legacy tranche).
6. Pool trading fee rate.
7. Exact qualifying amount and minimums (after the data review).
8. Bot/sniper exclusion rules.
9. Whether exchanges held the old token.
10. Final audit-firm list for the auto-audit rule.
11. Legal wrapper, jurisdiction and participation restrictions.
12. This repo's code license.
13. Private cost details (kept in the git-ignored file).

---

## 20. Glossary

- **Allowance:** the most the team can take from the treasury per month
  without a proposal.
- **Average price (TWAP):** the price averaged over time, so short spikes
  don't count.
- **Escrow:** a program that holds deposits under fixed rules. Nobody can take
  them outside those rules.
- **Futarchy:** decisions made by comparing "pass" and "fail" market prices
  instead of votes.
- **Merkle root:** a short fingerprint of a whole list. It lets a program
  check anyone's entry without storing the list, and the list can't be
  changed later.
- **Milestone:** a price level (2×, 4×…) that must be held on average before
  tokens are released.
- **Pro-rata:** everyone gets the same percentage of what they asked for.
- **Savings bank:** unspent allowance that can be drawn later, at most +20% of
  the allowance per month.
- **Snapshot:** a record of who held what at a past moment, from blockchain
  history.
- **Squads:** a widely used Solana multisig wallet program.
