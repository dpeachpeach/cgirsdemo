#!/bin/sh
# Runs every ported program's characterization suite.
# Fails if any individual suite fails; reports the full roster at the end.
set -e
cd "$(dirname "$0")"

failed=""
ran=""
for runner in */run-tests.sh; do
    [ -x "$runner" ] || continue
    program=$(dirname "$runner")
    echo "=== $program ==="
    ran="$ran $program"
    if ! "./$runner"; then
        failed="$failed $program"
    fi
done

if [ -z "$ran" ]; then
    echo "no program suites found under migration/" >&2
    exit 1
fi

echo "--- SUITES RUN:$ran ---"
if [ -n "$failed" ]; then
    echo "--- SUITES FAILED:$failed ---" >&2
    exit 1
fi
echo "--- ALL SUITES PASSED ---"
