#!/bin/sh
# FTDCALC characterization suite.  No GnuCOBOL needed: the expected values are
# captures of actual COBOL runs, held in fixtures/.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
