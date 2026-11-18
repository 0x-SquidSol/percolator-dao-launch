#!/bin/sh
# Run Anchor 0.29.0 for this repository by its exact versioned name, so the
# machine's default Anchor version is never switched. Install it once with
# `avm install 0.29.0` (then restore your default with `avm use <version>`).
set -e
ANCHOR="${HOME}/.avm/bin/anchor-0.29.0"
if [ ! -x "$ANCHOR" ]; then
  echo "Anchor 0.29.0 not found at $ANCHOR. Install it with: avm install 0.29.0" >&2
  exit 1
fi
cd "$(git rev-parse --show-toplevel)"
exec "$ANCHOR" "$@"
