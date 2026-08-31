#!/bin/sh
# Runs the ENTVAL characterization suite. No arguments, no COBOL required.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
