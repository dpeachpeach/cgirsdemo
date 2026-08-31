"""Characterization against the golden pair produced by the shipped data/ fixtures.

Input: data/MODEST.dat as step 060 (ESTPEN) left it.
Expected output: data/MODFRZ.dat, data/FRZEVAL.rpt and the step's console
counters, exactly as the COBOL wrote them.
"""

from __future__ import annotations

import pytest

from conftest import RECORD_LENGTH


def test_module_file_is_reproduced_byte_for_byte(shipped, shipped_run):
    assert shipped_run.out_data == shipped.modot


def test_report_file_is_reproduced_line_for_line(shipped, shipped_run):
    assert shipped_run.report_lines == shipped.report_lines


def test_console_counters_match_the_cobol_display_lines(shipped, shipped_run):
    assert shipped_run.stdout_text == shipped.stdout


def test_every_input_record_is_written_out(shipped, shipped_run):
    assert shipped_run.read_count == shipped_run.written_count == 52


def _record_ids(pair):
    return [rec[0:9].decode() + "-" + rec[9:11].decode() + "-" + rec[11:17].decode()
            for rec in pair.records_in()]


@pytest.mark.parametrize("index", range(52))
def test_each_module_record_matches_the_cobol_output_record(shipped, shipped_run, index):
    expected = shipped.records_out()[index]
    actual = shipped_run.out_records[index]
    assert actual == expected


def test_only_the_freeze_group_is_ever_modified(shipped, shipped_run):
    for source, produced in zip(shipped.records_in(), shipped_run.out_records):
        assert source[:58] == produced[:58]
        assert source[66:] == produced[66:]
        assert len(produced) == RECORD_LENGTH


def test_records_without_an_evaluated_freeze_produce_no_report_line(shipped, shipped_run):
    reported = {line[9:18] for line in shipped.report_lines}
    for source in shipped.records_in():
        frz = source[58:66].decode()
        has_evaluated_freeze = any(
            frz[position] == letter
            for position, letter in ((0, "A"), (2, "L"), (1, "V"), (4, "S"), (6, "Z"))
        )
        assert (source[0:9].decode() in reported) == has_evaluated_freeze
