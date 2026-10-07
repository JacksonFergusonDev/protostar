#!/usr/bin/env bash
# Scaffolds a built-in template in a fresh directory and checks that its first
# commit runs and passes the prek hooks Protostar installed.
#
# Usage: template-hooks-smoke.sh TEMPLATE PYTHON_VERSION
set -euo pipefail

template="$1"
python_version="$2"

temp_base="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
if command -v cygpath >/dev/null 2>&1; then
  temp_base=$(cygpath -u "$temp_base")
fi
smoke_dir="$temp_base/smoke_${template}"
rm -rf "$smoke_dir"
mkdir -p "$smoke_dir"
cd "$smoke_dir"

protostar init --template "$template" --prek --python-version "$python_version"

# 1. Verify pre-commit hook script was installed by Protostar
test -f .git/hooks/pre-commit || { echo "ERROR: .git/hooks/pre-commit missing"; exit 1; }

# Pre-stage all files so hooks have staged content to inspect
git add .

# 2. Canary test: verify commit-msg hook actively rejects non-conventional commit (when present)
if [ -f .git/hooks/commit-msg ]; then
  echo "=== Running commit-msg hook canary test ==="
  canary_code=0
  canary_output=$(git commit -m "invalid non-conventional commit message" < /dev/null 2>&1) || canary_code=$?
  if [ $canary_code -eq 0 ]; then
    echo "ERROR: commit-msg hook failed to reject invalid commit message"
    echo "$canary_output"
    exit 1
  else
    echo "Canary commit correctly rejected by commit-msg hook (exit code $canary_code)"
    echo "$canary_output"
  fi
fi

# 3. Verify clean first commit triggers prek hooks and succeeds
echo "=== Running valid initial commit ==="
commit_code=0
commit_output=$(git commit -m "feat: initial scaffold" < /dev/null 2>&1) || commit_code=$?
echo "$commit_output"

if [ $commit_code -ne 0 ]; then
  echo "ERROR: Initial commit failed with exit code $commit_code"
  exit 1
fi

# 4. Verify hook execution output is present in commit output
# A here-string has no upstream writer for grep's early exit to interrupt.
grep -qE "(uv lock check|ruff check|ruff format|Passed)" <<< "$commit_output" || {
  echo "ERROR: Prek hook execution not detected in commit output"
  exit 1
}
