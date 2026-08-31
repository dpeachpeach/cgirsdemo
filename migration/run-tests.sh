#!/bin/sh
# Runs every ported program's characterization suite.
# Fails if any program's suite fails; reports which ones did.
set -u
cd "$(dirname "$0")"

failed=""
found=0
for runner in */run-tests.sh; do
    [ -x "$runner" ] || continue
    found=$((found + 1))
    program=$(dirname "$runner")
    echo "=== $program ==="
    if ! "./$runner"; then
        failed="$failed $program"
    fi
done

if [ "$found" -eq 0 ]; then
    echo "*** no migration/*/run-tests.sh found" >&2
    exit 12
fi

if [ -n "$failed" ]; then
    echo "*** FAILED:$failed" >&2
    exit 1
fi

echo "--- ALL SUITES PASSED ($found programs) ---"
