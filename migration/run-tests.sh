#!/bin/sh
# Runs every ported program's characterization suite; fails if any suite fails.
set -e
cd "$(dirname "$0")"
rc=0
for suite in */run-tests.sh; do
    [ -x "$suite" ] || continue
    echo "=== $suite ==="
    if ! "./$suite"; then
        rc=1
    fi
done
exit $rc
