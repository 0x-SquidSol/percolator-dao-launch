// Creates the throwaway local test wallet Anchor.toml points at, in the
// git-ignored .anchor folder. Never use it for anything real.
// Experimental and unaudited.
import { Keypair } from "@solana/web3.js";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

const path = ".anchor/local-test-wallet.json";

if (existsSync(path)) {
  console.log(`${path} already exists; leaving it unchanged.`);
} else {
  mkdirSync(dirname(path), { recursive: true });
  const wallet = Keypair.generate();
  writeFileSync(path, JSON.stringify(Array.from(wallet.secretKey)), {
    mode: 0o600,
    flag: "wx",
  });
  console.log(`Created ${path} (throwaway local test key).`);
}
