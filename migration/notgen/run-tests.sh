#!/bin/sh
# Runs the NOTGEN characterization suite. No arguments, no environment setup
# beyond pytest; the COBOL-captured golden expectations live in fixtures/.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
