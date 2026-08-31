#!/bin/sh
# Runs the ENTVAL characterization suite. No arguments, no GnuCOBOL needed:
# the COBOL-captured expectations are baked into fixtures/.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
