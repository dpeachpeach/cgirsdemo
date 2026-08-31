#!/bin/sh
# Runs the STATCALC characterization suite. No arguments, no GnuCOBOL needed:
# expected values are frozen COBOL captures under fixtures/.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
