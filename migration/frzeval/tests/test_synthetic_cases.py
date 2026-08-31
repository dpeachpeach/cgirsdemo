"""Characterization of individual behaviours, using synthetic module records.

The records were hand-built in a scratch copy of the repo and fed to the
compiled COBOL FRZEVAL; ``fixtures/synthetic/`` holds that program's actual
output. Each test below states the behaviour and then asserts what the COBOL
did, whether or not it is what the rule would suggest.
"""

from __future__ import annotations

import pytest

TEXT = slice(36, 66)
FREEZE = slice(68, 76)


def balance_of(line):
    """The 13-character ZR-BAL field. LINE SEQUENTIAL strips the trailing
    blank a positive amount leaves in the sign position, so pad it back."""
    return line[78:].ljust(13)


@pytest.fixture(scope="module")
def check(synthetic, synthetic_run, synthetic_cases):
    """Assert the port reproduces the COBOL output for one synthetic case."""

    def _check(case_id):
        entry = synthetic_cases[case_id]
        index, ein = entry["index"], entry["ein"]
        expected_record = synthetic.records_out()[index]
        actual_record = synthetic_run.out_records[index]
        assert actual_record == expected_record, f"{case_id}: module record differs"
        expected_line = synthetic.report_line_for(ein)
        actual_lines = [line for line in synthetic_run.report_lines if line[9:18] == ein]
        actual_line = actual_lines[0] if actual_lines else None
        assert actual_line == expected_line, f"{case_id}: report line differs"
        return expected_record, expected_line

    return _check


def test_whole_synthetic_file_is_reproduced_byte_for_byte(synthetic, synthetic_run):
    assert synthetic_run.out_data == synthetic.modot
    assert synthetic_run.report_lines == synthetic.report_lines
    assert synthetic_run.stdout_text == synthetic.stdout


def test_unfrozen_module_is_passed_through_untouched_and_unreported(check):
    record, line = check("S01")
    assert record[58:66].decode() == "        "
    assert line is None


def test_a_freeze_suppresses_refund_only(check):
    record, line = check("S02")
    assert record[58:66].decode() == "A  R    "
    assert line[TEXT].strip() == "REFUND SUPPRESSED"


def test_v_freeze_suppresses_offset_only(check):
    record, line = check("S03")
    assert record[58:66].decode() == " V     O"
    assert line[TEXT].strip() == "OFFSET SUPPRESSED"


def test_l_freeze_suppresses_both_refund_and_offset(check):
    record, line = check("S04")
    assert record[58:66].decode() == "  LR   O"
    assert line[TEXT].strip() == "REFUND AND OFFSET SUPPRESSED"


def test_s_freeze_suppresses_refund_only(check):
    record, line = check("S05")
    assert record[58:66].decode() == "   RS   "
    assert line[TEXT].strip() == "REFUND SUPPRESSED"


def test_z_freeze_suppresses_both_refund_and_offset(check):
    record, line = check("S06")
    assert record[58:66].decode() == "   R  ZO"
    assert line[TEXT].strip() == "REFUND AND OFFSET SUPPRESSED"


def test_x_freeze_is_never_evaluated_and_produces_no_suppression(check):
    """The X position exists in the copybook but no branch in FRZEVAL reads it."""
    record, line = check("S07")
    assert record[58:66].decode() == "     X  "
    assert line is None


def test_all_five_evaluated_freezes_set_reports_the_combined_text_once(check):
    record, line = check("S08")
    assert record[58:66].decode() == "AVLRS ZO"
    assert line[TEXT].strip() == "REFUND AND OFFSET SUPPRESSED"


def test_refund_freeze_and_offset_freeze_combine_into_the_both_text(check):
    record, line = check("S09")
    assert record[58:66].decode() == "AV R   O"
    assert line[TEXT].strip() == "REFUND AND OFFSET SUPPRESSED"


def test_preexisting_r_and_o_positions_are_left_alone_and_not_reported(check):
    """R and O carried in from an earlier cycle do not themselves count as freezes."""
    record, line = check("S10")
    assert record[58:66].decode() == "   R   O"
    assert line is None


def test_lowercase_freeze_letters_do_not_match_the_uppercase_comparands(check):
    record, line = check("S11")
    assert record[58:66].decode() == "avl s z "
    assert line is None


def test_negative_balance_prints_with_a_trailing_minus_sign(check):
    record, line = check("S12")
    assert balance_of(line) == "      900.50-"


def test_report_balance_silently_drops_high_order_digits_beyond_nine(check):
    """WBAL holds 12345678901.23 but ZR-BAL is PIC ZZZZZZZZ9.99-, so the
    report shows 345678901.23. The COBOL has no ON SIZE ERROR and does not
    flag the truncation."""
    record, line = check("S13")
    assert balance_of(line) == "345678901.23 "


def test_balance_excludes_module_interest(check):
    """BMF-INT is 5000.00 on this record and does not appear in the balance:
    1000.00 + 11.11 + 22.22 + 33.33 - 300.33 - 99.67 = 666.66."""
    record, line = check("S14")
    assert balance_of(line) == "      666.66 "


def test_zero_balance_still_reports_when_a_freeze_is_present(check):
    record, line = check("S15")
    assert balance_of(line) == "        0.00 "


def test_large_negative_balance_is_truncated_and_keeps_its_sign(check):
    record, line = check("S16")
    assert balance_of(line) == "765432109.87-"


def test_one_cent_negative_balance_formats_without_leading_zeros(check):
    record, line = check("S17")
    assert balance_of(line) == "        0.01-"


def test_two_both_suppressing_freezes_are_counted_but_reported_once(check):
    record, line = check("S18")
    assert record[58:66].decode() == "  LR  ZO"
    assert line[TEXT].strip() == "REFUND AND OFFSET SUPPRESSED"


def test_balance_accumulator_wraps_when_the_sum_exceeds_eleven_whole_digits(check):
    """102999999999.96 does not fit PIC S9(11)V99; the COBOL stores
    02999999999.96 and the report edit field then shows 999999999.96."""
    record, line = check("S19")
    assert balance_of(line) == "999999999.96 "


def test_balance_at_the_report_edit_field_maximum_prints_in_full(check):
    record, line = check("S20")
    assert balance_of(line) == "999999999.99 "


def test_counters_include_a_record_once_per_suppression_kind(synthetic, synthetic_run):
    """RFND SUP and OFST SUP are independent counters; a record with both
    freezes increments both, so their sum exceeds the reported line count."""
    assert synthetic_run.refund_suppressed_count == 13
    assert synthetic_run.offset_suppressed_count == 10
    assert len(synthetic.report_lines) == 16
    assert synthetic_run.stdout_text == synthetic.stdout
