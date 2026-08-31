#!/bin/sh
# FTDCALC characterization suite.  Runs from a clean checkout with no
# arguments; needs neither GnuCOBOL nor a prior pipeline run.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
