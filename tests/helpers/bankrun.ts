// Shared test setup: an in-process Solana bank (solana-bankrun) with
// helpers to send transactions and move time. Experimental and unaudited.
import {
  Keypair,
  PublicKey,
  Transaction,
  TransactionInstruction,
} from "@solana/web3.js";
import { Clock, ProgramTestContext, start } from "solana-bankrun";

export const ONE_MINUTE = 60n;
export const ONE_HOUR = 60n * ONE_MINUTE;
export const ONE_DAY = 24n * ONE_HOUR;

/** A fresh bank. Programs under test are added here as they are written. */
export async function startBank(
  programs: { name: string; programId: PublicKey }[] = [],
): Promise<ProgramTestContext> {
  return start(programs, []);
}

/** Sends one transaction paid by the bank's payer and waits for it. */
export async function send(
  context: ProgramTestContext,
  instructions: TransactionInstruction[],
  signers: Keypair[] = [],
): Promise<void> {
  const tx = new Transaction();
  tx.recentBlockhash = context.lastBlockhash;
  tx.feePayer = context.payer.publicKey;
  tx.add(...instructions);
  tx.sign(context.payer, ...signers);
  await context.banksClient.processTransaction(tx);
}

/** The bank's current Unix time, in seconds. */
export async function now(context: ProgramTestContext): Promise<bigint> {
  return (await context.banksClient.getClock()).unixTimestamp;
}

/** Moves the bank's clock forward by `seconds`. */
export async function advanceTime(
  context: ProgramTestContext,
  seconds: bigint,
): Promise<void> {
  if (seconds < 0n) {
    throw new Error("advanceTime only moves forward");
  }
  const clock = await context.banksClient.getClock();
  context.setClock(
    new Clock(
      clock.slot,
      clock.epochStartTimestamp,
      clock.epoch,
      clock.leaderScheduleEpoch,
      clock.unixTimestamp + seconds,
    ),
  );
}

/** Moves the bank forward by `slots` (and gives it a fresh blockhash). */
export async function advanceSlots(
  context: ProgramTestContext,
  slots: bigint,
): Promise<void> {
  const clock = await context.banksClient.getClock();
  context.warpToSlot(clock.slot + slots);
}
