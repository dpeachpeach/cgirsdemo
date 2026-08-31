"""Golden-pair equivalence: the Python port must reproduce the COBOL byte for byte.

`fixtures/shipped` is the pair produced by `./run/pipeline.sh` on the fixtures as
shipped. `fixtures/synthetic` is the pair produced after appending the five
records in `fixtures/synthetic/MODMAST-appended.txt` to `data/MODMAST.txt` in a
scratch tree and re-running BLDFIX, ENTVAL, DUPCHK and STATCALC. Both expected
sides were captured from GnuCOBOL, never derived from the rule.
"""

import pytest

from helpers import Run


@pytest.fixture(scope="module", params=["shipped", "synthetic"])
def run(request):
    return Run(request.param)


def test_module_file_is_byte_identical_to_cobol_output(run):
    assert run.modstat == run.expected_modstat


def test_report_is_byte_identical_to_cobol_output(run):
    assert run.report == run.expected_report


def test_read_and_written_counts_match_cobol_displays(run):
    records = len(run.modin) // 150
    assert (run.job.r1, run.job.r2) == (records, records)


def test_suspend_counter_equals_report_line_count(run):
    assert run.job.r7 == len(run.report_lines())
