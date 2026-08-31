#!/bin/sh
# Runs the OVPINT characterization suite against the frozen COBOL goldens.
set -e
cd "$(dirname "$0")"
python3 -m pytest tests/ "$@"
