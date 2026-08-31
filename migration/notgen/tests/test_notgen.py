"""Characterization tests for the NOTGEN port.

Every expected value in this file was captured from GnuCOBOL 3.1.2 running
src/NOTGEN.cbl, either against the shipped data/ fixtures or against
synthetic fixture records added to a scratch copy of the repository (frozen
under fixtures/).  Expected values are never derived from the IRM or from
the rule as documented; where the COBOL is wrong the test asserts the wrong
answer and says so in its name.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from notgen import (
    ModuleRecord,
    format_amount_edited,
    run,
    select,
    unpack_comp3,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

PAIRS = ["shipped", "synthetic"]


def golden(pair, name):
    return FIXTURES / f"{pair}_{name}"


def load(pair):
    return run(golden(pair, "MODOFF.dat").read_bytes())


def report_line(pair, ein):
    lines = golden(pair, "NOTGEN.rpt").read_text().splitlines()
    return next(l for l in lines if l[8:17] == ein)


def module_record(pair, ein):
    raw = golden(pair, "MODOFF.dat").read_bytes()
    for off in range(0, len(raw), 150):
        if raw[off:off + 9].decode() == ein:
            return ModuleRecord.parse(raw[off:off + 150])
    raise AssertionError(ein)


# --- golden pairs: byte-for-byte equivalence --------------------------------


@pytest.mark.parametrize("pair", PAIRS)
def test_notice_file_matches_cobol_byte_for_byte(pair):
    assert load(pair).notices == golden(pair, "NOTICE.dat").read_bytes()


@pytest.mark.parametrize("pair", PAIRS)
def test_report_file_matches_cobol_byte_for_byte(pair):
    assert load(pair).report == golden(pair, "NOTGEN.rpt").read_text()


@pytest.mark.parametrize("pair", PAIRS)
def test_display_counters_match_cobol(pair):
    assert load(pair).console == golden(pair, "console.txt").read_text()


def test_shipped_counters_are_the_documented_cycle_numbers():
    result = load("shipped")
    assert (result.read_count, result.notice_count, result.suppress_count) == (52, 45, 3)


def test_report_carries_one_line_per_selected_module_not_per_module_read():
    # 52 modules read, 48 report lines: the WHEN OTHER fall-through leaves no
    # trace of the analysis in the report at all.
    result = load("shipped")
    lines = result.report.splitlines()
    assert len(lines) == 48
    assert result.read_count - len(lines) == 4


# --- branch-level behaviour, expected values read out of the goldens --------


def test_refund_freeze_A_wins_over_penalty_and_balance_selection():
    rec = module_record("shipped", "120001322")
    assert rec.frz_a == "A"
    sel = select(rec)
    assert (sel.cp, sel.severity) == ("0193", "3")
    assert "0193  DUPLICATE RETURN FILED" in report_line("shipped", "120001322")


def test_ftd_penalty_selects_cp0194_severity_2():
    sel = select(module_record("shipped", "120001112"))
    assert (sel.cp, sel.severity, sel.suppressed) == ("0194", "2", False)
    assert report_line("shipped", "120001112").endswith("117159.53   2")


def test_ftf_penalty_selects_cp0215_severity_2():
    sel = select(module_record("shipped", "200001210"))
    assert (sel.cp, sel.severity) == ("0215", "2")
    assert "0215  CIVIL PENALTY ASSESSED" in report_line("shipped", "200001210")


def test_overpayment_below_minus_100_selects_cp0267():
    sel = select(module_record("shipped", "100001077"))
    assert (sel.cp, sel.severity) == ("0267", "1")
    assert sel.balance == Decimal("-64130.30")
    assert report_line("shipped", "100001077").endswith("64130.30-  1")


def test_balance_due_over_100_selects_cp0161():
    # Uncovered by the shipped fixtures; synthetic module 990001001 was added
    # to the scratch tree and the pipeline re-run to capture this.
    sel = select(module_record("synthetic", "990001001"))
    assert (sel.cp, sel.severity, sel.balance) == ("0161", "1", Decimal("500.00"))
    assert "0161  BALANCE DUE" in report_line("synthetic", "990001001")


def test_module_within_plus_or_minus_100_produces_no_notice_and_no_report_line():
    sel = select(module_record("synthetic", "990001002"))
    assert sel.balance == Decimal("100.00")
    assert sel.cp == "    "
    assert sel.notice is None and sel.report is None
    assert "990001002" not in golden("synthetic", "NOTGEN.rpt").read_text()


def test_refund_freeze_R_suppresses_only_the_overpayment_notice():
    suppressed = select(module_record("shipped", "200001007"))
    assert (suppressed.cp, suppressed.suppressed) == ("0267", True)
    assert "SUPPRESSED BY FREEZE" in report_line("shipped", "200001007")

    # Same R freeze, balance-due selection: not suppressed.
    kept = select(module_record("synthetic", "990001003"))
    assert module_record("synthetic", "990001003").frz_r == "R"
    assert (kept.cp, kept.suppressed) == ("0161", False)
    assert "0161  BALANCE DUE" in report_line("synthetic", "990001003")


def test_freeze_Z_suppresses_every_notice_class():
    sel = select(module_record("shipped", "200001329"))
    assert (sel.cp, sel.suppressed) == ("0194", True)
    assert "SUPPRESSED BY FREEZE" in report_line("shipped", "200001329")

    sel = select(module_record("synthetic", "990001004"))
    assert (sel.cp, sel.suppressed) == ("0161", True)
    assert "SUPPRESSED BY FREEZE" in report_line("synthetic", "990001004")


def test_suppressed_module_writes_report_line_but_no_notice_record():
    result = load("shipped")
    assert result.suppress_count == 3
    notices = result.notices
    eins = {notices[i:i + 9].decode() for i in range(0, len(notices), 100)}
    assert "200001007" not in eins
    assert "SUPPRESSED BY FREEZE" in report_line("shipped", "200001007")


# --- defects reproduced -----------------------------------------------------


def test_report_amount_truncates_the_tenth_integer_digit():
    # WBAL is PIC S9(11)V99 but NR-AMT is PIC ZZZZZZZZ9.99- (nine integer
    # digits).  A 1.23 billion dollar balance is reported as 234,567,890.12.
    line = report_line("synthetic", "990001006")
    assert line.endswith("234567890.12   1")
    sel = select(module_record("synthetic", "990001006"))
    assert sel.balance == Decimal("1234567890.12")
    # The notice record keeps the untruncated amount, so the two outputs of
    # the same step disagree about the same module.
    notice = next(
        n for n in
        [load("synthetic").notices[i:i + 100]
         for i in range(0, len(load("synthetic").notices), 100)]
        if n[0:9] == b"990001006"
    )
    assert unpack_comp3(notice[60:67], 13, 2) == Decimal("1234567890.12")


def test_notice_date_is_a_hardcoded_2026_literal_not_the_cycle_date():
    # 2200-BLD does MOVE 20260815 TO DVP-GREG for every record, so every
    # notice in every cycle carries julian 2026229 (2026-08-17, the Monday
    # after that Saturday).
    notices = load("shipped").notices
    dates = {notices[i + 67:i + 74].decode() for i in range(0, len(notices), 100)}
    assert dates == {"2026229"}


def test_report_severity_column_is_blank_only_for_unselected_modules():
    # Severity is derived from the CP code, so a suppressed module still
    # reports the severity of the notice that was never mailed.
    assert report_line("shipped", "200001007").endswith("697.52-  1")


# --- arithmetic / edited-field helpers --------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("0.00"), "        0.00 "),
        (Decimal("500.00"), "      500.00 "),
        (Decimal("-64130.30"), "    64130.30-"),
        (Decimal("1234567890.12"), "234567890.12 "),
        (Decimal("-1234567890.12"), "234567890.12-"),
    ],
)
def test_edited_amount_matches_cobol_picture_zzzzzzzz9_99_minus(value, expected):
    assert format_amount_edited(value) == expected


def test_balance_uses_exact_decimal_arithmetic_with_no_rounding():
    rec = module_record("shipped", "100001077")
    sel = select(rec)
    assert sel.liability == rec.assd + rec.pftd + rec.pftf + rec.pftp
    assert sel.balance == sel.liability - rec.dep - rec.crd - rec.interest
