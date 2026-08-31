"""Characterization tests for the CAWRMTCH port.

Every expected value in this file was captured from GnuCOBOL 3.1.2 running
src/CAWRMTCH.cbl — the report images and DISPLAY counter lines under
fixtures/ are verbatim program output. Nothing here is derived from the IRM or
from the rule as anybody understands it, and defects in the legacy behavior are
asserted as-is under names that say so.

Fixture sets:
  shipped      — the repository's own data/ fixtures, pipeline run unmodified
  synthetic_a  — shipped plus four modules and two W-2 records added to reach
                 the branches the shipped fixtures never execute
  synthetic_b  — synthetic_a plus a duplicate W-2 for a matched group and an
                 exact-tolerance-boundary group
"""

from decimal import Decimal
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cawrmtch import edit_signed, edit_unsigned, run, truncate  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SETS = ["shipped", "synthetic_a", "synthetic_b"]


def cobol_run(name):
    root = FIXTURES / name
    lines, counters = run(root / "MODOFF.dat", root / "CAWRW2.txt")
    return lines, counters


def expected_report(name):
    text = (FIXTURES / name / "CAWRMTCH.rpt.expected").read_text(encoding="ascii")
    return text.splitlines()


def expected_counters(name):
    return (FIXTURES / name / "counters.txt").read_text(encoding="ascii").splitlines()


def find(lines, ein, year):
    return [l for l in lines if l[10:19] == ein and l[20:24] == year]


@pytest.mark.parametrize("name", SETS)
def test_report_image_matches_cobol_byte_for_byte(name):
    lines, _ = cobol_run(name)
    assert lines == expected_report(name)


@pytest.mark.parametrize("name", SETS)
def test_display_counters_match_cobol(name):
    _, counters = cobol_run(name)
    assert counters.display_lines() == expected_counters(name)


def test_modules_with_mft_other_than_01_are_excluded_from_the_match():
    """8100-RDMOD skips every non-MFT-01 module; 52 records yield 45 groups."""
    modoff = (FIXTURES / "shipped" / "MODOFF.dat").read_bytes()
    records = [modoff[i:i + 150] for i in range(0, len(modoff), 150)]
    assert len(records) == 52
    assert sum(1 for r in records if r[9:11] == b"01") == 45
    _, counters = cobol_run("shipped")
    assert counters.groups_941 == 45


def test_control_break_sums_every_mft01_module_for_one_ein_and_year():
    lines, _ = cobol_run("synthetic_a")
    # two modules, 100000.00 + 50000.00, reported as a single group
    row = find(lines, "990001111", "2023")
    assert len(row) == 1
    assert row[0][71:83] == "   150000.00"  # CR-941
    assert row[0][26:30] == "C001"


def test_group_with_no_ssa_w2_reports_c004_with_negative_difference():
    lines, _ = cobol_run("synthetic_a")
    row = find(lines, "990002222", "2023")[0]
    assert row[26:30] == "C004"
    assert row[32:56].rstrip() == "NO W2 DATA FROM SSA"
    assert row[58:70] == "        0.00"  # CR-W2 is zero-filled
    assert row.endswith("12345.67-")


def test_trailing_941_group_after_w2_end_of_file_reports_c004():
    """WKEY is HIGH-VALUES after W-2 EOF, so the remaining modules take 4100."""
    lines, _ = cobol_run("synthetic_a")
    row = find(lines, "993005555", "2023")[0]
    assert row[26:30] == "C004"
    assert row.endswith("777.77-")


def test_c004_groups_are_counted_as_discrepancies_not_as_their_own_bucket():
    """C5 lumps 941-only groups in with out-of-tolerance matches."""
    _, shipped = cobol_run("shipped")
    _, synth = cobol_run("synthetic_a")
    assert shipped.discrepant == 18
    assert synth.discrepant == 20  # the same 18 plus the two C004 groups


def test_tolerance_floor_is_hardcoded_100_dollars():
    """WTOL = liability * 1%, floored at 100 regardless of module size."""
    lines, _ = cobol_run("shipped")
    # 1% of 507.53 is 5.07, but the floor makes the 115.75 difference the test
    small_out = find(lines, "940001161", "2023")[0]
    assert small_out[26:30] == "C003"
    # 1% of 445.18 is 4.45; 2.15 is inside the 100 floor and reported in balance
    small_in = find(lines, "920001315", "2023")[0]
    assert small_in[26:30] == "C001"


def test_difference_exactly_equal_to_tolerance_is_in_balance():
    """4000-CMP uses NOT > WTOL, so the boundary falls on the in-balance side."""
    lines, _ = cobol_run("synthetic_b")
    row = find(lines, "994007777", "2023")[0]
    assert row[26:30] == "C001"
    assert row[71:83] == "   200000.00"
    assert row.rstrip().endswith("2000.00")


def test_zero_difference_prints_unsigned_zero():
    lines, _ = cobol_run("synthetic_a")
    row = find(lines, "990001111", "2023")[0]
    assert row.endswith("        0.00")


def test_second_w2_for_a_matched_ein_year_is_reported_as_having_no_941_module():
    """Legacy defect: the merge advances past the group, so a duplicate W-2 is
    reported C005 even though an MFT 01 module for that EIN and year exists."""
    lines, counters = cobol_run("synthetic_b")
    rows = find(lines, "990001111", "2023")
    assert [r[26:30] for r in rows] == ["C001", "C005"]
    assert rows[1][32:56].rstrip() == "W2 FILED - NO 941 MODULE"
    assert rows[1][71:83] == "        0.00"  # liability reported as zero
    assert counters.w2_only == 6


def test_w2_only_rows_report_the_difference_as_positive_withholding():
    lines, _ = cobol_run("shipped")
    row = find(lines, "279000026", "2023")[0]
    assert row[26:30] == "C005"
    assert row.endswith("11662.56")


def test_report_lines_carry_no_page_headings_or_totals():
    """The report is detail-only: every line starts with the program name."""
    for name in SETS:
        lines, _ = cobol_run(name)
        assert lines
        assert all(l.startswith("CAWRMTCH  ") for l in lines)


def test_tolerance_percentage_truncates_instead_of_rounding():
    """COMPUTE WTOL = WLIA * 0.01 has no ROUNDED, so the scale-2 store truncates."""
    assert truncate(Decimal("125467.24") * Decimal("0.01"), 11, 2) == Decimal("1254.67")
    assert truncate(Decimal("-0.999"), 11, 2) == Decimal("-0.99")


def test_edited_amount_fields_suppress_high_order_zeros_and_the_sign():
    """CR-W2 and CR-941 are PIC ZZZZZZZZ9.99 — unsigned — and CR-DIFF adds a
    trailing sign position."""
    assert edit_unsigned(Decimal("0")) == "        0.00"
    assert edit_unsigned(Decimal("325143.69")) == "   325143.69"
    assert edit_unsigned(Decimal("-576.42")) == "      576.42"
    assert edit_signed(Decimal("-2020.12")) == "     2020.12-"
    assert edit_signed(Decimal("2020.12")) == "     2020.12 "
