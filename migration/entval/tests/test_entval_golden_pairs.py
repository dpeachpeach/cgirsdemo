"""One test per golden pair captured from the compiled COBOL ENTVAL.

Cases:
  shipped  - data/ENTMAST.txt as it ships in the repository (52 records)
  synth_a  - synthetic fixture, 20 records, uncovered-branch batch A
  synth_b  - synthetic fixture, 10 records, uncovered-branch batch B
  synth_c  - synthetic fixture, 3 records, blank digits in ENT-FYM
  empty    - zero-record input file
"""

import pytest

from golden import expected_console, expected_output, expected_report, run_case

CASES = ["shipped", "synth_a", "synth_b", "synth_c", "empty"]


@pytest.mark.parametrize("case", CASES)
def test_entval_output_file_matches_cobol(case):
    assert run_case(case).output_bytes == expected_output(case)


@pytest.mark.parametrize("case", CASES)
def test_entval_error_report_matches_cobol(case):
    assert run_case(case).report_text == expected_report(case)


@pytest.mark.parametrize("case", CASES)
def test_entval_console_counters_match_cobol(case):
    assert run_case(case).console == expected_console(case)
