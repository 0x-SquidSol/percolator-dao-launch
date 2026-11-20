// The TypeScript claim-list code must match the shared vectors exactly.
// Experimental and unaudited.
import { PublicKey } from "@solana/web3.js";
import { assert } from "chai";
import { readFileSync } from "node:fs";
import { DOMAINS, MAX_PROOF_LEN, build, leaf, verify } from "../scripts/lib/merkle.js";

interface VectorEntry {
  wallet: string;
  amount: string;
  index: number;
  leaf: string;
  proof: string[];
}

const vectors = JSON.parse(readFileSync("docs/spec/merkle-vectors.json", "utf8")) as {
  domains: Record<string, string>;
  max_proof_len: number;
  cases: { name: string; domain: string; distribution: string; root: string; entries: VectorEntry[] }[];
  must_fail: { why: string; leaf: string; proof: string[]; root: string }[];
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
    assert.throws(() => leaf(d, dist, w, 1n << 64n, 0), /non-zero u64/);
    assert.throws(() => leaf(d, dist, w, 1n, 2 ** 32), /u32/);
    assert.throws(() => leaf(d, dist, w, 1n, -1), /u32/);
  });
});
