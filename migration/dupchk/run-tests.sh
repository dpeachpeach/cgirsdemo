#!/bin/sh
# Characterization suite for the DUPCHK port. No arguments, no GnuCOBOL needed.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
