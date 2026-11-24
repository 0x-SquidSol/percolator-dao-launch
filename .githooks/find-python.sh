# Sourced by the git hooks: pick a working Python 3.8+ that the repository
# can't replace. Hooks run from the top folder, and files committed there
# must never stand in for any program the hooks run.
#
# So PATH keeps only absolute folders outside the repository: "." or a
# relative folder points into it (Git Bash keeps Windows' relative entries),
# and so does a venv or any other folder inside it, since a pull can
# overwrite ignored files. Until PATH is clean, only shell built-ins run.

# Whether folder $1 is the top folder or inside it, compared by identity
# (-ef), so links, junctions and letter case can't hide it.
inside_top() {
  up=$1  # (sh has no local variables: a name of its own)
  while :; do
    [ "$up" -ef . ] && return 0
    case "$up" in
      /) return 1 ;;
      */*) up=${up%/*}; [ -n "$up" ] || up=/ ;;
      *) return 1 ;;
    esac
  done
}

clean_path=""
saved_ifs=$IFS
IFS=:
set -f  # no wildcard expansion of PATH folders
for folder in $PATH; do
  case "$folder" in
    /*) ;;
    *) continue ;;  # relative or empty
  esac
  [ -d "$folder" ] || continue
  # Also where it leads: a link or junction outside may point inside.
  real=$(cd -P -- "$folder" 2>/dev/null && pwd -P) || continue
  if inside_top "$folder" || inside_top "$real"; then
    continue
  fi
  clean_path="${clean_path:+$clean_path:}$folder"
done
set +f
IFS=$saved_ifs
PATH=$clean_path
export PATH

# Version-manager shims read files in the current folder (.python-version,
# .tool-versions, mise.toml) to choose a python, and some accept a path, so
# a commit could point them inside the repository. Use the system python.
PYENV_VERSION=system ASDF_PYTHON_VERSION=system MISE_PYTHON_VERSION=system
export PYENV_VERSION ASDF_PYTHON_VERSION MISE_PYTHON_VERSION

PY=""
for candidate in python3 python py; do
  if "$candidate" -I -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "guard: Python 3.8+ is required for the commit hooks" >&2
  exit 1
fi
