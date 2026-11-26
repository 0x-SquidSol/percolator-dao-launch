// Claim-list (merkle) format, exactly as specified in docs/spec/merkle.md:
// leaf and node hashing, tree building and proof checking. Used by the list
// building scripts and the claim page; checked against the Rust verifier and
// the Python reference in CI. Experimental and unaudited.
import { PublicKey } from "@solana/web3.js";
import { createHash } from "node:crypto";

export const LEAF_PREFIX = 0x00;
export const NODE_PREFIX = 0x01;
export const MAX_PROOF_LEN = 24;

export const DOMAINS = {
  guaranteed: "percolator-dao-launch/guaranteed/v1",
  "legacy-tranche": "percolator-dao-launch/legacy-tranche/v1",
  "weekly-drop": "percolator-dao-launch/weekly-drop/v1",
} as const;

const U64_MAX = (1n << 64n) - 1n;
const U32_MAX = (1n << 32n) - 1n;

export interface Entry {
  wallet: PublicKey;
  amount: bigint;
  index: number;
}

function sha256(...parts: Uint8Array[]): Buffer {
  const hash = createHash("sha256");
  for (const part of parts) {
    hash.update(part);
  }
  return hash.digest();
}

function le(value: bigint, bytes: number): Buffer {
  const out = Buffer.alloc(bytes);
  let rest = value;
  for (let i = 0; i < bytes; i++) {
    out[i] = Number(rest & 0xffn);
    rest >>= 8n;
  }
  return out;
}

/** The leaf hash of one entry. Throws on out-of-range fields. */
export function leaf(
  domain: string,
  distribution: PublicKey,
  wallet: PublicKey,
  amount: bigint,
  index: number,
): Buffer {
  // Checked before converting: Buffer.from(_, "ascii") keeps only the low
  // byte of other characters, so a different string could give a real tag.
  if (typeof domain !== "string" || !/^[\x00-\x7f]{1,255}$/.test(domain)) {
    throw new Error("domain must be 1-255 ASCII bytes");
  }
  const tag = Buffer.from(domain, "ascii");
  if (amount <= 0n || amount > U64_MAX) {
    throw new Error("amount must be a non-zero u64");
  }
  if (!Number.isInteger(index) || index < 0 || BigInt(index) > U32_MAX) {
    throw new Error("index must be a u32");
  }
  return sha256(
    Buffer.from([LEAF_PREFIX, tag.length]),
    tag,
    distribution.toBuffer(),
    wallet.toBuffer(),
    le(amount, 8),
    le(BigInt(index), 4),
  );
}

/** Combines two hashes; the smaller (as unsigned bytes) goes first. */
export function node(a: Buffer, b: Buffer): Buffer {
  const [low, high] = Buffer.compare(a, b) <= 0 ? [a, b] : [b, a];
  return sha256(Buffer.from([NODE_PREFIX]), low, high);
}

export interface Tree {
  root: Buffer;
  /** Proof for each leaf, keyed by the leaf's hex hash. */
  proofs: Map<string, Buffer[]>;
}

/** Builds the tree for a list. Rejects empty lists, zero amounts and
 * duplicate (wallet, index) pairs. */
export function build(domain: string, distribution: PublicKey, entries: Entry[]): Tree {
  if (entries.length === 0) {
    throw new Error("a list must have at least one entry");
  }
  const seen = new Set<string>();
  for (const e of entries) {
    const key = `${e.wallet.toBase58()}:${e.index}`;
    if (seen.has(key)) {
      throw new Error("duplicate (wallet, index) entry");
    }
    seen.add(key);
  }
  const leaves = entries
    .map((e) => leaf(domain, distribution, e.wallet, e.amount, e.index))
    .sort(Buffer.compare);
  const proofs = new Map<string, Buffer[]>(leaves.map((l) => [l.toString("hex"), []]));
  let level: { hash: Buffer; members: string[] }[] = leaves.map((l) => ({
    hash: l,
    members: [l.toString("hex")],
  }));
  while (level.length > 1) {
    const above: typeof level = [];
    for (let i = 0; i + 1 < level.length; i += 2) {
      const left = level[i]!;
      const right = level[i + 1]!;
      for (const m of left.members) proofs.get(m)!.push(right.hash);
      for (const m of right.members) proofs.get(m)!.push(left.hash);
      above.push({ hash: node(left.hash, right.hash), members: [...left.members, ...right.members] });
    }
    if (level.length % 2 === 1) {
      above.push(level[level.length - 1]!); // odd one out moves up unchanged
    }
    level = above;
  }
  return { root: level[0]!.hash, proofs };
}

/** Whether `proof` leads from `candidate` to `root`. Rejects proofs longer
 * than MAX_PROOF_LEN. */
export function verify(proof: Buffer[], root: Buffer, candidate: Buffer): boolean {
  if (proof.length > MAX_PROOF_LEN) {
    return false;
  }
  let hash = candidate;
  for (const sibling of proof) {
    hash = node(hash, sibling);
  }
  return hash.equals(root);
}
