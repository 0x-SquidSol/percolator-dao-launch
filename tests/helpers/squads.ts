// Squads v4 in the test bank, loaded from the fixtures that
// scripts/fetch-fixtures.ts downloads and checks (run `yarn fixtures`).
// Squads is called, never copied (AGPL-3.0). Experimental and unaudited.
import * as multisig from "@sqds/multisig";
import { PublicKey } from "@solana/web3.js";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { AddedAccount } from "solana-bankrun";

export const SQUADS_PROGRAM_ID = new PublicKey(
  "SQDS4ep65T869zMMBKyuUq6aD6EgTu8psMjkvj52pCf",
);
export const SQUADS_PROGRAM_CONFIG = multisig.getProgramConfigPda({})[0];

const FIXTURES = join("tests", "fixtures");

function fixture(file: string): Buffer {
  const path = join(FIXTURES, file);
  if (!existsSync(path)) {
    throw new Error(`missing ${path}: run \`yarn fixtures\` first`);
  }
  return readFileSync(path);
}

/** The Squads program, for startBank's `programs` argument. */
export function squadsProgram(): { name: string; programId: PublicKey } {
  fixture("squads_multisig.so"); // fail early with a clear message if absent
  return { name: "squads_multisig", programId: SQUADS_PROGRAM_ID };
}

/** The Squads ProgramConfig account, for startBank's `accounts` argument. */
export function squadsAccounts(): AddedAccount[] {
  return [
    {
      address: SQUADS_PROGRAM_CONFIG,
      info: {
        data: fixture("squads-program-config"),
        owner: SQUADS_PROGRAM_ID,
        executable: false,
        lamports: 1_000_000_000,
      },
    },
  ];
}
