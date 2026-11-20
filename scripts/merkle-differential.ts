// Differential check between the TypeScript claim-list code and the Rust
// verifier: TypeScript builds random lists, Rust rebuilds and checks them
// (same roots and proofs, every proof accepted) and writes its own random
// lists, which TypeScript then rebuilds and checks the same way. A random
// seed is printed so any failure can be replayed with `--seed <n>`.
// Run from the repository root (Linux/WSL). Experimental and unaudited.
import { PublicKey } from "@solana/web3.js";
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DOMAINS, build, leaf, verify, type Entry } from "./lib/merkle.js";

const U64_MAX = (1n << 64n) - 1n;
const U32_MAX = 2 ** 32 - 1;

/** xorshift64* with BigInt, so lists are reproducible from the seed. */
class Rng {
  private state: bigint;
  constructor(seed: bigint) {
    this.state = (seed | 1n) & U64_MAX;
  }
  next(): bigint {
    let x = this.state;
    x ^= x >> 12n;
    x ^= (x << 25n) & U64_MAX;
    x ^= x >> 27n;
    this.state = x;
    return (x * 0x2545f4914f6cdd1dn) & U64_MAX;
  }
  below(n: number): number {
    return Number(this.next() % BigInt(n));
  }
  key(): PublicKey {
    const bytes = Buffer.alloc(32);
    for (let i = 0; i < 4; i++) {
      bytes.writeBigUInt64LE(this.next(), i * 8);
    }
    return new PublicKey(bytes);
  }
}

interface ListFile {
  producer: "typescript" | "rust";
  seed: string;
  lists: {
    domain: string;
    distribution: string;
    root: string;
    entries: { wallet: string; amount: string; index: number; leaf: string; proof: string[] }[];
  }[];
}

const domains = Object.values(DOMAINS);

function generate(seed: bigint): ListFile {
  const rng = new Rng(seed);
  const lists: ListFile["lists"] = [];
  for (let n = 0; n < 200; n++) {
    const size = n % 25 === 0 ? 500 + rng.below(1000) : 1 + rng.below(40);
    const domain = domains[rng.below(domains.length)]!;
    const distribution = rng.key();
    const entries: Entry[] = [];
    for (let i = 0; i < size; i++) {
      const pick = rng.below(10);
      const amount = pick === 0 ? U64_MAX : pick === 1 ? 1n : rng.next() || 1n;
      const kind = rng.below(4);
      const index = kind === 0 ? U32_MAX : kind === 1 ? 0 : rng.below(8);
      entries.push({ wallet: rng.key(), amount, index });
    }
    const tree = build(domain, distribution, entries);
    lists.push({
      domain,
      distribution: distribution.toBase58(),
      root: tree.root.toString("hex"),
      entries: entries.map((e) => {
        const l = leaf(domain, distribution, e.wallet, e.amount, e.index).toString("hex");
        return {
          wallet: e.wallet.toBase58(),
          amount: e.amount.toString(),
          index: e.index,
          leaf: l,
          proof: tree.proofs.get(l)!.map((p) => p.toString("hex")),
        };
      }),
    });
  }
  return { producer: "typescript", seed: seed.toString(), lists };
}

function check(file: ListFile): number {
  if (file.producer !== "rust" || file.lists.length === 0) {
    throw new Error("expected a non-empty list file from Rust");
  }
  let checked = 0;
  for (const list of file.lists) {
    const distribution = new PublicKey(list.distribution);
    const entries = list.entries.map((e) => ({
      wallet: new PublicKey(e.wallet),
      amount: BigInt(e.amount),
      index: e.index,
    }));
    const tree = build(list.domain, distribution, entries);
    if (tree.root.toString("hex") !== list.root) {
      throw new Error(`root differs for a Rust list (${list.domain})`);
    }
    for (const e of list.entries) {
      const l = leaf(list.domain, distribution, new PublicKey(e.wallet), BigInt(e.amount), e.index);
      if (l.toString("hex") !== e.leaf) throw new Error("leaf differs");
      const ours = tree.proofs.get(e.leaf)!.map((p) => p.toString("hex"));
      if (JSON.stringify(ours) !== JSON.stringify(e.proof)) throw new Error("proof differs");
      const proof = e.proof.map((p) => Buffer.from(p, "hex"));
      if (!verify(proof, Buffer.from(list.root, "hex"), l)) throw new Error("proof rejected");
      checked++;
    }
  }
  return checked;
}

function main(): void {
  const seedArg = process.argv.indexOf("--seed");
  const seed =
    seedArg >= 0 ? BigInt(process.argv[seedArg + 1]!) : randomBytes(8).readBigUInt64LE();
  console.log(`differential seed: ${seed} (replay with --seed ${seed})`);

  const dir = mkdtempSync(join(tmpdir(), "merkle-diff-"));
  const tsPath = join(dir, "typescript.json");
  const rustPath = join(dir, "rust.json");
  const ours = generate(seed);
  writeFileSync(tsPath, JSON.stringify(ours));
  const tsEntries = ours.lists.reduce((sum, l) => sum + l.entries.length, 0);
  console.log(`typescript wrote ${ours.lists.length} lists (${tsEntries} entries)`);

  execFileSync(
    "cargo",
    ["test", "-p", "dao_common", "--locked", "--test", "merkle_differential", "--", "--ignored", "--nocapture"],
    { stdio: "inherit", env: { ...process.env, DIFF_IN: tsPath, DIFF_OUT: rustPath, DIFF_SEED: seed.toString() } },
  );

  const checked = check(JSON.parse(readFileSync(rustPath, "utf8")) as ListFile);
  console.log(`typescript checked ${checked} Rust entries: all match`);
}

main();
