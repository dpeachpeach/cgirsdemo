#!/bin/sh
# Captures golden pairs by running the COBOL NOTGEN in the scratch tree.
set -e
cd "$(dirname "$0")"
DEST=$HOME/repos/cgirsdemo/migration/notgen/fixtures
export COB_LIBRARY_PATH="$PWD/bin"

capture() {
    name=$1
    mkdir -p "$DEST/$name"
    cp data/MODOFF.dat "$DEST/$name/MODOFF.dat"
    ./bin/NOTGEN > "$DEST/$name/counters.txt"
    cp data/NOTICE.dat "$DEST/$name/NOTICE.dat"
    cp data/NOTGEN.rpt "$DEST/$name/NOTGEN.rpt"
    echo "captured $name"
}

cp /tmp/MODOFF.golden.dat data/MODOFF.dat
capture shipped

python3 gensyn.py > /dev/null
capture synthetic_selection

python3 gensyn2.py > /dev/null
capture synthetic_edge

python3 gennib.py > /dev/null
capture sign_nibbles

cp /tmp/MODOFF.golden.dat data/MODOFF.dat
