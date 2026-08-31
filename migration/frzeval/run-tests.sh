#!/bin/sh
# Runs the FRZEVAL characterization suite. No arguments, no GnuCOBOL needed:
# the COBOL-captured goldens are frozen under fixtures/.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
