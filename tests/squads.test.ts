// Checks the Squads fixture: a real Squads v4 program in the test bank can
// create a multisig. Experimental and unaudited.
import * as multisig from "@sqds/multisig";
import { Keypair, PublicKey } from "@solana/web3.js";
import { assert } from "chai";
import { ProgramTestContext } from "solana-bankrun";
import { send, startBank } from "./helpers/bankrun.js";
import {
  SQUADS_PROGRAM_CONFIG,
  SQUADS_PROGRAM_ID,
  squadsAccounts,
  squadsProgram,
} from "./helpers/squads.js";

const { Permission, Permissions } = multisig.types;

describe("squads fixture", function () {
  let context: ProgramTestContext;

  beforeEach(async function () {
    context = await startBank([squadsProgram()], squadsAccounts());
  });

  it("loads the Squads program", async function () {
    const program = await context.banksClient.getAccount(SQUADS_PROGRAM_ID);
    assert.isNotNull(program);
    assert.isTrue(program?.executable);
  });

  it("creates a 2-of-3 multisig with an execute-only member", async function () {
    const config = await context.banksClient.getAccount(SQUADS_PROGRAM_CONFIG);
    assert.isNotNull(config);
    const [programConfig] = multisig.accounts.ProgramConfig.fromAccountInfo({
      ...config!,
      data: Buffer.from(config!.data),
    });

    const createKey = Keypair.generate();
    const [multisigPda] = multisig.getMultisigPda({ createKey: createKey.publicKey });
    const alice = Keypair.generate().publicKey;
    const bob = Keypair.generate().publicKey;
    const executor = Keypair.generate().publicKey;

    await send(
      context,
      [
        multisig.instructions.multisigCreateV2({
          treasury: programConfig.treasury,
          createKey: createKey.publicKey,
          creator: context.payer.publicKey,
          multisigPda,
          configAuthority: null,
          threshold: 2,
          members: [
            { key: alice, permissions: Permissions.all() },
            { key: bob, permissions: Permissions.all() },
            { key: executor, permissions: Permissions.fromPermissions([Permission.Execute]) },
          ],
          timeLock: 0,
          rentCollector: null,
        }),
      ],
      [createKey],
    );

    const account = await context.banksClient.getAccount(multisigPda);
    assert.isNotNull(account);
    const [created] = multisig.accounts.Multisig.fromAccountInfo({
      ...account!,
      data: Buffer.from(account!.data),
    });
    assert.equal(created.threshold, 2);
    assert.equal(created.members.length, 3);
    assert.isTrue(created.configAuthority.equals(PublicKey.default));

    // The vault address follows the documented seeds:
    // ["multisig", multisig, "vault", 0u8].
    const [vault] = multisig.getVaultPda({ multisigPda, index: 0 });
    const [expected] = PublicKey.findProgramAddressSync(
      [Buffer.from("multisig"), multisigPda.toBuffer(), Buffer.from("vault"), Buffer.from([0])],
      SQUADS_PROGRAM_ID,
    );
    assert.isTrue(vault.equals(expected));
  });
});
