# tests

> [!CAUTION]
> Experimental, unaudited code for an experiment that may never be used.
> Nothing here means anything will launch.

TypeScript tests for the on-chain programs, run against an in-process Solana
bank ([solana-bankrun](https://github.com/kevinheavey/solana-bankrun)) with
mocha. They run on Linux (WSL on Windows), the same as CI.

## Setup, once per machine

- Node.js **22.23.5** (see `engines` in `package.json`), with Corepack
  enabled so the pinned yarn version is used.
- `yarn install --frozen-lockfile`. Packages may not run install scripts
  (see `.yarnrc`).
- `yarn test-wallet` creates the throwaway local test key at
  `.anchor/local-test-wallet.json` (git-ignored). Never use it for anything
  real.

## Running

```sh
yarn test        # all tests
yarn typecheck   # type-check tests and scripts
```

CI runs both on every push (`.github/workflows/typescript.yml`), along with
the JavaScript dependency audit described in `scripts/README.md`.

## Helpers (`helpers/`)

- `bankrun.ts`: start a bank, send transactions, move time
  (`advanceTime`) and slots (`advanceSlots`).
- `tokens.ts`: mints, associated token accounts, balances, and a USDC
  stand-in at the real USDC address (`createUsdcMock`). Amounts use 6
  decimals: `tokens(1_000)` is 1,000 tokens.
