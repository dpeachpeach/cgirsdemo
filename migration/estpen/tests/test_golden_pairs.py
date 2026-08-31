"""Whole-file equivalence against the three COBOL-captured golden pairs."""

import pytest

import estpen

PAIRS = ["shipped", "synthpipe", "direct"]


@pytest.mark.parametrize("pair", PAIRS)
def test_modest_file_is_byte_identical_to_cobol(goldens, pair):
    modin, modest, _, _ = goldens[pair]
    out, _, _ = estpen.process(modin)
    assert out == modest


@pytest.mark.parametrize("pair", PAIRS)
def test_report_file_is_identical_to_cobol(goldens, pair):
    modin, _, rpt, _ = goldens[pair]
    _, text, _ = estpen.process(modin)
    assert text == rpt


@pytest.mark.parametrize("pair", PAIRS)
def test_end_of_job_counters_match_cobol_display(goldens, pair):
    modin, _, _, expected = goldens[pair]
    _, _, counters = estpen.process(modin)
    assert (counters.read, counters.written, counters.assessed) == expected


def test_report_lines_stop_at_column_82_like_line_sequential(goldens):
    _, _, rpt, _ = goldens["shipped"]
    _, text, _ = estpen.process(goldens["shipped"][0])
    assert {len(line) for line in text.splitlines()} == {82}
    assert text.splitlines() == rpt.splitlines()
