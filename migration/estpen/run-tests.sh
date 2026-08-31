#!/bin/sh
# Characterization suite for the ESTPEN port. No arguments, no setup
# beyond pytest; the COBOL-captured expectations live in fixtures/.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
