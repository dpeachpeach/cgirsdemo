#!/bin/sh
# Runs the CAWRMTCH characterization suite. No arguments, no GnuCOBOL needed:
# the expected values under fixtures/ were captured from the COBOL build.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
