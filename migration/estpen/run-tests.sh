#!/bin/sh
# Runs the ESTPEN characterization suite. No arguments, no GnuCOBOL needed:
# the expected values are frozen COBOL output under fixtures/.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
