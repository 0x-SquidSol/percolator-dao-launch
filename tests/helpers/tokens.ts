// Token helpers for tests: mints, associated token accounts and a stand-in
// for USDC at its real mainnet address. Experimental and unaudited.
import {
  AccountLayout,
  MINT_SIZE,
  MintLayout,
  TOKEN_PROGRAM_ID,
  createAssociatedTokenAccountIdempotentInstruction,
  createInitializeMint2Instruction,
  createMintToInstruction,
  getAssociatedTokenAddressSync,
} from "@solana/spl-token";
import { Keypair, PublicKey, SystemProgram } from "@solana/web3.js";
import { ProgramTestContext } from "solana-bankrun";
import { send } from "./bankrun.js";

/** Standard decimals for test mints (and USDC). */
export const DECIMALS = 6;

/** Canonical mainnet USDC mint. Programs check for this exact address. */
export const USDC_MINT = new PublicKey(
  "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
);

/** Whole tokens to base units at 6 decimals: tokens(1_000) = 1_000_000_000n. */
export function tokens(whole: number): bigint {
  if (!Number.isSafeInteger(whole) || whole < 0) {
    throw new Error("tokens() takes a non-negative whole number");
  }
  return BigInt(whole) * 10n ** BigInt(DECIMALS);
}

/** Creates a new mint with `authority` as mint authority and no freeze authority. */
export async function createMint(
  context: ProgramTestContext,
  authority: PublicKey,
  decimals = DECIMALS,
): Promise<PublicKey> {
  const mint = Keypair.generate();
  const rent = await context.banksClient.getRent();
  await send(
    context,
    [
      SystemProgram.createAccount({
        fromPubkey: context.payer.publicKey,
        newAccountPubkey: mint.publicKey,
        lamports: Number(rent.minimumBalance(BigInt(MINT_SIZE))),
        space: MINT_SIZE,
        programId: TOKEN_PROGRAM_ID,
      }),
      createInitializeMint2Instruction(mint.publicKey, decimals, authority, null),
    ],
    [mint],
  );
  return mint.publicKey;
}

/**
 * Puts a USDC stand-in at the real USDC address, with `authority` as its
 * mint authority, so tests can mint "USDC" freely.
 */
export async function createUsdcMock(
  context: ProgramTestContext,
  authority: PublicKey,
): Promise<PublicKey> {
  const data = Buffer.alloc(MINT_SIZE);
  MintLayout.encode(
    {
      mintAuthorityOption: 1,
      mintAuthority: authority,
      supply: 0n,
      decimals: DECIMALS,
      isInitialized: true,
      freezeAuthorityOption: 0,
      freezeAuthority: PublicKey.default,
    },
    data,
  );
  const rent = await context.banksClient.getRent();
  context.setAccount(USDC_MINT, {
    lamports: Number(rent.minimumBalance(BigInt(MINT_SIZE))),
    data,
    owner: TOKEN_PROGRAM_ID,
    executable: false,
  });
  return USDC_MINT;
}

/** Creates (if needed) and returns `owner`'s associated token account. */
export async function createAta(
  context: ProgramTestContext,
  mint: PublicKey,
  owner: PublicKey,
): Promise<PublicKey> {
  const ata = getAssociatedTokenAddressSync(mint, owner, true);
  await send(context, [
    createAssociatedTokenAccountIdempotentInstruction(
      context.payer.publicKey,
      ata,
      owner,
      mint,
    ),
  ]);
  return ata;
}

/** Mints `amount` base units to `owner`'s associated token account. */
export async function mintTo(
  context: ProgramTestContext,
  mint: PublicKey,
  authority: Keypair,
  owner: PublicKey,
  amount: bigint,
): Promise<PublicKey> {
  const ata = await createAta(context, mint, owner);
  await send(
    context,
    [createMintToInstruction(mint, ata, authority.publicKey, amount)],
    [authority],
  );
  return ata;
}

/** A token account's balance in base units. */
export async function balance(
  context: ProgramTestContext,
  tokenAccount: PublicKey,
): Promise<bigint> {
  const account = await context.banksClient.getAccount(tokenAccount);
  if (account === null) {
    throw new Error(`token account ${tokenAccount.toBase58()} does not exist`);
  }
  return AccountLayout.decode(account.data).amount;
}
