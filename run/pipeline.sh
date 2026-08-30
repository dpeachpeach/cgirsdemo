#!/bin/sh
# Runs the nightly cycle in the order the JCL would submit it.
# The JCL under jcl/ is decorative; this is the real orchestration.
set -e
cd "$(dirname "$0")/.."
export COB_LIBRARY_PATH="$PWD/bin"
for step in BLDFIX ENTVAL DUPCHK STATCALC FTDCALC PENCALC ESTPEN \
            FRZEVAL OVPINT OFFSET CAWRMTCH NOTGEN; do
    if [ -x "bin/$step" ]; then
        echo "--- STEP $step ---"
        "bin/$step"
    else
        echo "*** $step not built" >&2
        exit 12
    fi
done
echo "--- CYCLE COMPLETE ---"
