"""One test per golden pair: the Python port must reproduce the COBOL report
and the COBOL DISPLAY counters byte for byte.

`shipped` is the pair produced by the fixtures in data/ as committed. The `s*`
pairs are synthetic inputs constructed to reach branches the shipped fixtures
never execute; every expected value was captured by running the COBOL.
"""

import pytest

from conftest import GOLDEN_PAIRS, cobol_counters, cobol_report, python_run


@pytest.mark.parametrize("pair", GOLDEN_PAIRS)
def test_cawrmtch_report_matches_cobol(pair):
    lines, _ = python_run(pair)
    assert lines == cobol_report(pair)


@pytest.mark.parametrize("pair", GOLDEN_PAIRS)
def test_cawrmtch_counters_match_cobol(pair):
    _, counters = python_run(pair)
    assert counters == cobol_counters(pair)
