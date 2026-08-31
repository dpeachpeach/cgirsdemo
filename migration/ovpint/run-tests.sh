#!/bin/sh
# Runs the OVPINT characterization suite.  No arguments, no GnuCOBOL needed:
# the COBOL-captured expectations live in fixtures/.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
