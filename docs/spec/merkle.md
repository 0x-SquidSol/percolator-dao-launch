# Spec: claim lists (merkle format)

> [!CAUTION]
> Experimental, unaudited design for an experiment that may never be used.
> Nothing here means any raise, token, claim or drop will happen.

This spec fixes how a list of payouts ("wallet A is owed 500") is turned
into one 32-byte **root** that goes on-chain, and how one entry is proven to
be on the list. Every implementation (the on-chain programs, the scripts that
build lists, the claim page) must follow it exactly, and all are tested
against the shared vectors in [`merkle-vectors.json`](merkle-vectors.json).

It contains no formulas: who is owed what is decided off-chain, and any list
that follows these rules works.

## Kinds of list

Each list has a **domain**, a fixed label naming what it is for, so an entry
from one kind of list can never be accepted by another.

| Domain (ASCII) | Used by | `distribution` field | `index` field |
|---|---|---|---|
| `percolator-dao-launch/guaranteed/v1` | Raise program: guaranteed deposit amounts | The Raise account address | Always `0` |
| `percolator-dao-launch/legacy-tranche/v1` | Claims program: legacy tranche releases | The Raise account address | The release number (`0`, `1`, ...) |
| `percolator-dao-launch/weekly-drop/v1` | Claims program: weekly drops | That week's distributor account address | Always `0` |

A changed layout gets a new domain (`/v2`), never a silent change to `/v1`.

## Hash function

SHA-256 everywhere (`solana_program::hash::hashv` on-chain).

## Entries (leaves)

An entry has: `wallet` (32-byte public key), `amount` (u64, base units) and
`index` (u32). Its leaf hash is:

```
leaf = SHA-256(
    0x00                      # leaf prefix, 1 byte
 || len(domain)               # 1 byte
 || domain                    # ASCII bytes
 || distribution              # 32 bytes
 || wallet                    # 32 bytes
 || amount                    # 8 bytes, little-endian
 || index                     # 4 bytes, little-endian
)
```

Binding the domain and the distribution account means an entry cannot be
replayed on another kind of list, another raise or another week. Binding
the index means each tranche release is a separate entry, claimable once.

## Combining (internal nodes)

```
node(a, b) = SHA-256( 0x01 || min(a, b) || max(a, b) )
```

`min`/`max` compare the 32-byte hashes as unsigned bytes, left to right.
Because each pair is sorted, a proof needs no left/right flags.

The different prefixes (`0x00` for leaves, `0x01` for nodes) stop a known
attack where a node is passed off as a leaf (a "second preimage" attack).
Leaf inputs are also always longer than node inputs (at least 79 bytes
against 65).

## Building a tree

1. Reject the list if it is empty, if any `amount` is `0`, or if any
   `(wallet, index)` pair appears twice.
2. Hash every entry into its leaf.
3. Sort the leaf hashes ascending. The root therefore does not depend on the
   order of the input list.
4. Repeat until one hash is left: combine neighbours pairwise with `node`,
   left to right; if a level has an odd count, the last hash moves up
   unchanged.
5. The last hash is the **root**. A one-entry list's root is its leaf.

## Proofs

A proof is the list of sibling hashes from the leaf up to the root, skipping
levels where the hash moved up unchanged. To verify:

```
h = leaf
for each sibling s in proof:
    h = node(h, s)
valid if h == root
```

On-chain programs must also:
- reject proofs longer than **24** hashes (enough for 16.7 million entries);
- recompute the leaf themselves from the claim's own fields (domain fixed
  by the instruction, `distribution` from the account being claimed
  against, `wallet` from the signer), never accept a leaf hash from the
  caller;
- record each claim (per `distribution`, `wallet` and `index`) so it can't
  be claimed twice.

## Test vectors

[`merkle-vectors.json`](merkle-vectors.json) is written by `merkle_reference.py generate`, from the
independent reference implementation in
[`scripts/spec/merkle_reference.py`](../../scripts/spec/merkle_reference.py)
and checked in CI to be up to date. Each case lists its entries, leaf
hashes, root and every proof, plus cases that must fail: a changed amount
or index, the same entry under another domain or distribution, a proof from
another list, and a proof over the length limit.

The proof check alone would accept an internal node presented as a leaf;
that attack is stopped by programs always recomputing the leaf from the
claim's fields (see [Proofs](#proofs)), which cannot produce a node hash
because of the different prefixes.
