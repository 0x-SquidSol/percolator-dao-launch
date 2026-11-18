# Sourced by the git hooks: pick a working Python 3.8+.
PY=""
for candidate in python3 python py; do
  if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "guard: Python 3.8+ is required for the commit hooks" >&2
  exit 1
fi
