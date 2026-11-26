// The TypeScript claim-list code must match the shared vectors exactly.
// Experimental and unaudited.
import { PublicKey } from "@solana/web3.js";
import { assert } from "chai";
import { readFileSync } from "node:fs";
import { DOMAINS, MAX_PROOF_LEN, build, leaf, node, verify } from "../scripts/lib/merkle.js";

interface VectorEntry {
  wallet: string;
  amount: string;
  index: number;
  leaf: string;
  proof: string[];
}

interface ProofVector {
  why: string;
  leaf: string;
  proof: string[];
  root: string;
}

const vectors = JSON.parse(readFileSync("docs/spec/merkle-vectors.json", "utf8")) as {
  domains: Record<string, string>;
  max_proof_len: number;
  cases: { name: string; domain: string; distribution: string; root: string; entries: VectorEntry[] }[];
  must_fail: ProofVector[];
  at_limit: ProofVector;
  over_limit: ProofVector;
};

const hex = (h: string) => Buffer.from(h, "hex");

describe("claim-list format (TypeScript)", function () {
  it("uses the spec's domains and limits", function () {
    assert.deepEqual(vectors.domains, { ...DOMAINS });
    assert.equal(vectors.max_proof_len, MAX_PROOF_LEN);
  });

  it("matches every vector leaf, root and proof", function () {
    assert.isAtLeast(vectors.cases.length, 6);
    for (const c of vectors.cases) {
      const distribution = new PublicKey(c.distribution);
      const entries = c.entries.map((e) => ({
        wallet: new PublicKey(e.wallet),
        amount: BigInt(e.amount),
        index: e.index,
      }));
      const tree = build(c.domain, distribution, entries);
      assert.equal(tree.root.toString("hex"), c.root, c.name);
      for (const e of c.entries) {
        const l = leaf(c.domain, distribution, new PublicKey(e.wallet), BigInt(e.amount), e.index);
        assert.equal(l.toString("hex"), e.leaf);
        assert.deepEqual(tree.proofs.get(e.leaf)!.map((p) => p.toString("hex")), e.proof);
        assert.isTrue(verify(e.proof.map(hex), hex(c.root), l), c.name);
      }
    }
  });

  it("rejects every must-fail vector", function () {
    assert.isAtLeast(vectors.must_fail.length, 6);
    for (const bad of vectors.must_fail) {
      assert.isFalse(verify(bad.proof.map(hex), hex(bad.root), hex(bad.leaf)), bad.why);
    }
  });

  it("accepts a proof of exactly the limit and rejects one step over it", function () {
    const ok = vectors.at_limit;
    const long = vectors.over_limit;
    assert.deepInclude(vectors.must_fail, long);
    assert.lengthOf(ok.proof, MAX_PROOF_LEN);
    assert.lengthOf(long.proof, MAX_PROOF_LEN + 1);
    for (const v of [ok, long]) {
      // Each root is the one its proof leads to, so only the length check
      // can reject the longer one.
      const root = v.proof.map(hex).reduce<Buffer>((h, s) => node(h, s), hex(v.leaf));
      assert.equal(root.toString("hex"), v.root);
    }
    assert.isTrue(verify(ok.proof.map(hex), hex(ok.root), hex(ok.leaf)));
    assert.isFalse(verify(long.proof.map(hex), hex(long.root), hex(long.leaf)));
  });

  it("checks the proof length limit itself", function () {
    const start = hex(vectors.cases[0]!.entries[0]!.leaf);
    const siblings = Array.from({ length: MAX_PROOF_LEN + 1 }, (_, n) => Buffer.alloc(32, n + 1));
    const fold = (proof: Buffer[]) => proof.reduce<Buffer>((h, s) => node(h, s), start);
    const full = siblings.slice(0, MAX_PROOF_LEN);
    assert.isTrue(verify(full, fold(full), start));
    // Would verify if the length were not checked.
    assert.isFalse(verify(siblings, fold(siblings), start));
  });

  it("rejects invalid lists and fields", function () {
    const d = DOMAINS["weekly-drop"];
    const dist = PublicKey.default;
    const w = new PublicKey(vectors.cases[0]!.entries[0]!.wallet);
    assert.throws(() => build(d, dist, []), /at least one entry/);
    assert.throws(
      () => build(d, dist, [{ wallet: w, amount: 1n, index: 0 }, { wallet: w, amount: 2n, index: 0 }]),
      /duplicate/,
    );
    assert.throws(() => leaf(d, dist, w, 0n, 0), /non-zero u64/);
    // Its low bytes spell the real domain, so it must not be accepted.
    assert.throws(() => leaf(d.split("/").join("į"), dist, w, 1n, 0), /ASCII/);
    assert.throws(() => leaf("", dist, w, 1n, 0), /ASCII/);
    assert.throws(() => leaf("x".repeat(256), dist, w, 1n, 0), /ASCII/);
    assert.lengthOf(leaf("x".repeat(255), dist, w, 1n, 0), 32);
    assert.throws(() => leaf(d, dist, w, 1n << 64n, 0), /non-zero u64/);
    assert.throws(() => leaf(d, dist, w, 1n, 2 ** 32), /u32/);
    assert.throws(() => leaf(d, dist, w, 1n, -1), /u32/);
  });
});
