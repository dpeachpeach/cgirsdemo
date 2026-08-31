"""Whole-file equivalence between the Python port and the captured COBOL runs."""

import pytest


@pytest.fixture(params=["shipped", "synthetic", "synthetic_negative"])
def pair(request):
    return request.getfixturevalue(request.param)


def test_module_output_file_is_byte_identical(pair):
    assert pair.run().modout == pair.modout


def test_report_file_is_line_identical(pair):
    assert pair.run().report == pair.report


def test_display_counters_match(pair):
    assert pair.run().counters == pair.counters


def test_every_input_module_is_written_unchanged_in_length(pair):
    result = pair.run()
    assert len(result.modout) == len(pair.modin)
    assert result.counters["read"] == result.counters["written"]


def test_only_the_ftd_penalty_field_is_modified(pair):
    """FTDCALC rewrites BMF-PFTD (offset 99, 6 bytes) and nothing else."""
    result = pair.run()
    for offset in range(0, len(pair.modin), 150):
        before = pair.modin[offset : offset + 150]
        after = result.modout[offset : offset + 150]
        assert before[:99] == after[:99]
        assert before[105:] == after[105:]
