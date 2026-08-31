#!/bin/sh
# Runs the STATCALC characterization suite. No arguments, clean checkout.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/ "$@"
