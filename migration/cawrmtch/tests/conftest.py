"""Path setup and shared helpers for the CAWRMTCH characterization suite.

The suite is hermetic: it reads the committed fixtures under
migration/cawrmtch/fixtures/ and never compiles or runs COBOL.
"""

import sys
from pathlib import Path

PORT_DIR = Path(__file__).resolve().parent.parent
FIXTURES = PORT_DIR / "fixtures"

if str(PORT_DIR) not in sys.path:
    sys.path.insert(0, str(PORT_DIR))

import pytest  # noqa: E402

from cawrmtch import run_match  # noqa: E402

GOLDEN_PAIRS = [
    "shipped",
    "s1_941only",
    "s2_multimodule",
    "s3_dup_w2",
    "s4_tolerance",
    "s5_overflow",
]


def cobol_report(pair):
    """Expected report lines as the COBOL wrote them."""
    return (FIXTURES / pair / "CAWRMTCH.rpt").read_text().splitlines()


def cobol_counters(pair):
    """Expected DISPLAY counter lines as the COBOL wrote them."""
    return (FIXTURES / pair / "counters.txt").read_text().splitlines()


def python_run(pair):
    directory = FIXTURES / pair
    lines, counters = run_match(directory / "MODOFF.dat", directory / "CAWRW2.txt")
    return lines, counters


def fields(line):
    """Split a report line on the CRPT displacements from src/CAWRMTCH.cbl."""
    padded = line.ljust(97)
    return {
        "ein": padded[10:19],
        "year": padded[20:24],
        "code": padded[26:30],
        "text": padded[32:56].rstrip(),
        "w2": padded[58:70],
        "liability": padded[71:83],
        "difference": padded[84:97],
    }


def select(lines, ein, year, code=None):
    """Every report line for an EIN / tax year (and optionally condition code)."""
    out = []
    for line in lines:
        parsed = fields(line)
        if parsed["ein"] == ein and parsed["year"] == year:
            if code is None or parsed["code"] == code:
                out.append(parsed)
    return out


def only(pair, ein, year, code=None):
    """The single matching line, asserted identical in the port and in the COBOL."""
    python_lines, _ = python_run(pair)
    from_python = select(python_lines, ein, year, code)
    from_cobol = select(cobol_report(pair), ein, year, code)
    assert from_python == from_cobol, "port diverges from the captured COBOL output"
    assert len(from_cobol) == 1, f"expected one line, got {len(from_cobol)}"
    return from_cobol[0]


@pytest.fixture
def golden():
    """Returns (python_lines, python_counters, cobol_lines, cobol_counters)."""

    def _golden(pair):
        lines, counters = python_run(pair)
        return lines, counters, cobol_report(pair), cobol_counters(pair)

    return _golden
