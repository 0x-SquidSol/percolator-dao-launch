// Downloads the outside programs and accounts the tests need from Solana
// mainnet into tests/fixtures (git-ignored), and refuses any file whose
// SHA-256 does not match the pinned value. Nothing downloaded is committed.
// See tests/README.md. Experimental and unaudited.
//
// If a pin fails, the program or account changed on mainnet (for example a
// Squads upgrade). Review the change before updating the pin.
import { Connection, PublicKey } from "@solana/web3.js";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const RPC_URL = process.env.SOLANA_RPC_URL ?? "https://api.mainnet-beta.solana.com";
const OUT_DIR = join("tests", "fixtures");
const UPGRADEABLE_LOADER = new PublicKey("BPFLoaderUpgradeab1e11111111111111111111111");
const PROGRAM_DATA_HEADER = 45; // UpgradeableLoaderState::ProgramData metadata

interface Fixture {
  file: string;
  address: string;
  kind: "program" | "account";
  sha256: string;
  about: string;
}

const FIXTURES: Fixture[] = [
  {
    file: "squads_multisig.so",
    address: "SQDS4ep65T869zMMBKyuUq6aD6EgTu8psMjkvj52pCf",
    kind: "program",
    // Same bytes as MetaDAO's committed fixture. Trailing-zero-trimmed hash
    // d48660833989ecea3145ff726164fe640bd90696f03ce00dfd0cda258cbf2fac matches
    // the OtterSec registry entry for Squads-Protocol/v4 commit 3742e55.
    sha256: "dec8d3e0fae58c7c8f2416e5f67c25e673f047afd6dd2bba4a47e0b29a01d34c",
    about: "Squads v4 multisig program (AGPL-3.0; called, never copied)",
  },
  {
    file: "squads-program-config",
    address: "BSTq9w3kZwNwpBXJEvTZz2G9ZTNyKBvoSeXMvwb4cNZr",
    kind: "account",
    sha256: "ba8e7712f069f2e68e8583b105ac2eb22d791265440da56df32f9f3f734af3e0",
    about: "Squads v4 ProgramConfig account (creation fee, treasury)",
  },
];

function sha256(data: Uint8Array): string {
  return createHash("sha256").update(data).digest("hex");
}

/** The public RPC sometimes drops requests: try a few times before failing. */
async function withRetries<T>(what: string, attempt: () => Promise<T>): Promise<T> {
  const tries = 4;
  for (let i = 1; ; i++) {
    try {
      return await attempt();
    } catch (error) {
      if (i >= tries) {
        throw new Error(`${what}: failed after ${tries} tries: ${String(error)}`);
      }
      await new Promise((resolve) => setTimeout(resolve, 2_000 * i));
    }
  }
}

async function download(connection: Connection, fixture: Fixture): Promise<Uint8Array> {
  return withRetries(fixture.file, () => downloadOnce(connection, fixture));
}

async function downloadOnce(connection: Connection, fixture: Fixture): Promise<Uint8Array> {
  const address = new PublicKey(fixture.address);
  const account = await connection.getAccountInfo(address, "finalized");
  if (account === null) {
    throw new Error(`${fixture.file}: ${fixture.address} not found on mainnet`);
  }
  if (fixture.kind === "account") {
    return account.data;
  }
  // An upgradeable program account points at its ProgramData account, which
  // holds the program bytes after a fixed header.
  if (!account.owner.equals(UPGRADEABLE_LOADER) || account.data.readUInt32LE(0) !== 2) {
    throw new Error(`${fixture.file}: not an upgradeable program account`);
  }
  const programData = new PublicKey(account.data.subarray(4, 36));
  const data = await connection.getAccountInfo(programData, "finalized");
  if (data === null) {
    throw new Error(`${fixture.file}: program data account not found`);
  }
  return data.data.subarray(PROGRAM_DATA_HEADER);
}

async function main(): Promise<void> {
  mkdirSync(OUT_DIR, { recursive: true });
  const connection = new Connection(RPC_URL, "finalized");
  let failed = false;
  for (const fixture of FIXTURES) {
    const path = join(OUT_DIR, fixture.file);
    if (existsSync(path) && sha256(readFileSync(path)) === fixture.sha256) {
      console.log(`ok       ${fixture.file} (already present)`);
      continue;
    }
    const data = await download(connection, fixture);
    const actual = sha256(data);
    if (actual !== fixture.sha256) {
      console.error(
        `MISMATCH ${fixture.file}: expected ${fixture.sha256}, got ${actual}.` +
          " It changed on mainnet; review before updating the pin.",
      );
      failed = true;
      continue;
    }
    writeFileSync(path, data);
    console.log(`fetched  ${fixture.file} (${data.length} bytes, sha256 ok)`);
  }
  if (failed) {
    process.exit(1);
  }
}

main().catch((error: unknown) => {
  console.error(String(error));
  process.exit(1);
});
