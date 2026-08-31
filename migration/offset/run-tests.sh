#!/bin/sh
# Runs the OFFSET characterization suite. No arguments, no setup beyond pytest.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
