#!/bin/sh
# Runs the FRZEVAL characterization suite. No arguments, no environment setup
# beyond pytest; the COBOL-captured expectations live in fixtures/.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
