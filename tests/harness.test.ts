// Checks the test harness itself: the bank starts, time moves, and the
// token helpers and USDC stand-in work. Experimental and unaudited.
import { Keypair } from "@solana/web3.js";
import { assert } from "chai";
import { ProgramTestContext } from "solana-bankrun";
import {
  ONE_DAY,
  advanceSlots,
  advanceTime,
  now,
  startBank,
} from "./helpers/bankrun.js";
import {
  USDC_MINT,
  balance,
  createMint,
  createUsdcMock,
  mintTo,
  tokens,
} from "./helpers/tokens.js";

describe("test harness", function () {
  let context: ProgramTestContext;

  beforeEach(async function () {
    context = await startBank();
  });

  it("moves time forward", async function () {
    const before = await now(context);
    await advanceTime(context, 7n * ONE_DAY);
    assert.equal(await now(context), before + 7n * ONE_DAY);
  });

  it("refuses to move time backward", async function () {
    try {
      await advanceTime(context, -1n);
      assert.fail("expected advanceTime to throw");
    } catch (error) {
      assert.include(String(error), "only moves forward");
    }
  });

  it("moves slots forward", async function () {
    const before = (await context.banksClient.getClock()).slot;
    await advanceSlots(context, 100n);
    assert.equal((await context.banksClient.getClock()).slot, before + 100n);
  });

  it("mints USDC at the real USDC address", async function () {
    const authority = Keypair.generate();
    const user = Keypair.generate();
    const mint = await createUsdcMock(context, authority.publicKey);
    assert.isTrue(mint.equals(USDC_MINT));

    const ata = await mintTo(context, mint, authority, user.publicKey, tokens(1_000));
    assert.equal(await balance(context, ata), 1_000_000_000n);
  });

  it("creates a mint and mints to a new holder", async function () {
    const authority = Keypair.generate();
    const user = Keypair.generate();
    const mint = await createMint(context, authority.publicKey);

    const ata = await mintTo(context, mint, authority, user.publicKey, tokens(100));
    assert.equal(await balance(context, ata), 100_000_000n);
  });
});
