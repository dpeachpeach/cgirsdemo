#!/bin/sh
# Runs the DUPCHK characterization suite against the golden captures in
# fixtures/. GnuCOBOL is not required: the expectations were captured from the
# COBOL when the fixtures were built.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/
