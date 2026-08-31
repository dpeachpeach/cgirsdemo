import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = PACKAGE_ROOT / "fixtures"

TESTS_DIR = Path(__file__).resolve().parent

for path in (PACKAGE_ROOT, TESTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
