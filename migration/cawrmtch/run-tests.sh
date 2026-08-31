#!/bin/sh
# Runs the CAWRMTCH characterization suite. Hermetic: no COBOL, no network.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
