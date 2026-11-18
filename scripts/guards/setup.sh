#!/bin/sh
# One-time setup for each clone: turn on the leak guards.
set -e
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
# Make any attempt to stage a *.private.* file fail, even with `git add -f`.
git config filter.blockprivate.clean false
git config filter.blockprivate.smudge cat
git config filter.blockprivate.required true
if [ ! -f private/guard-patterns.txt ]; then
  echo "Note: private/guard-patterns.txt is missing. Get it privately from a"
  echo "maintainer. Commits are refused until it exists."
fi
echo "Leak guards enabled."
