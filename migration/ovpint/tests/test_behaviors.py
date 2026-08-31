"""Per-branch characterization tests for OVPINT.

Each expected string below is a verbatim line of an OVPINT.rpt produced by
the compiled COBOL, or a value decoded from the COBOL's MODINT.dat.  Tests
whose names say something looks wrong are asserting a legacy defect on
purpose; the corresponding proposed fixes are listed in the port report and
are deliberately not applied.
"""

from decimal import Decimal

import pytest
from conftest import FIXTURES

from ovpint import BmfMod, availability_date, process_record


def load(name):
    raw = (FIXTURES / f"{name}_MODFRZ.dat").read_bytes()
    out = (FIXTURES / f"{name}_MODINT.dat").read_bytes()
    records = {}
    for i in range(0, len(raw), 150):
        rec = BmfMod(raw[i : i + 150])
        records[rec.ein] = (rec, BmfMod(out[i : i + 150]))
    return records


SHIPPED = load("shipped")
SYNTHETIC = load("synthetic")


def result_for(pool, ein):
    record, cobol_out = pool[ein]
    return record, cobol_out, process_record(record)


# --------------------------------------------------------------------------
# Interest allowed
# --------------------------------------------------------------------------
def test_interest_allowed_line_matches_cobol():
    _, _, res = result_for(SHIPPED, "100001077")
    assert res.report_line.rstrip() == (
        "OVPINT  100001077 10 202306  O802  "
        "OVERPAYMENT INTEREST ALLOW      53000.25 1095   11130.05"
    )


def test_allowed_interest_is_stored_in_the_module_record():
    _, cobol_out, res = result_for(SHIPPED, "100001077")
    assert res.record.interest == Decimal("11130.05") == cobol_out.interest


def test_report_text_is_truncated_to_twenty_six_characters():
    """OR-TXT is PIC X(26) but the literal moved into it is 28 characters,
    so every interest line reads 'OVERPAYMENT INTEREST ALLOW'."""
    _, _, res = result_for(SHIPPED, "100001077")
    assert "OVERPAYMENT INTEREST ALLOW " in res.report_line
    assert "ALLOWED" not in res.report_line


def test_interest_period_drops_the_first_thirty_days():
    """WNDY is reduced by 30 before the interest computation, and the
    reduced figure -- not the elapsed count -- is what the report shows."""
    record, _, res = result_for(SHIPPED, "100001077")
    elapsed = 1125  # 2023-07-17 availability to the 2026-08-15 cycle date
    assert availability_date(record.txpd) == 20230717
    assert res.report_line.split()[-2] == str(elapsed - 30)


def test_interest_is_rounded_half_up_not_truncated():
    """182.50 * 0.0700 * 457 / 365 is exactly 15.995; the COBOL wrote
    16.00, so the ROUNDED clause rounds half away from zero."""
    _, cobol_out, res = result_for(SYNTHETIC, "990000006")
    assert res.record.interest == Decimal("16.00") == cobol_out.interest


# --------------------------------------------------------------------------
# 45-day rule
# --------------------------------------------------------------------------
def test_forty_five_day_rule_line_matches_cobol():
    _, _, res = result_for(SHIPPED, "100001119")
    assert res.report_line.rstrip() == (
        "OVPINT  100001119 01 202606  O801  "
        "45 DAY RULE - NO INTEREST       23639.71   31       0.00"
    )


def test_forty_five_day_rule_leaves_the_module_record_untouched():
    record, cobol_out, res = result_for(SHIPPED, "100001119")
    assert res.record.raw == record.raw == cobol_out.raw


# --------------------------------------------------------------------------
# No overpayment
# --------------------------------------------------------------------------
def test_liabilities_above_deposits_produce_no_report_line():
    record, cobol_out, res = result_for(SHIPPED, "100001308")
    assert res.report_line is None
    assert res.record.raw == record.raw == cobol_out.raw


def test_overpayment_of_exactly_zero_produces_no_report_line():
    """WOVP is tested with NOT > ZERO, so a break-even module is silent."""
    record, cobol_out, res = result_for(SYNTHETIC, "990000005")
    assert record.dep - record.assd == Decimal("0.00")
    assert res.report_line is None
    assert res.record.raw == cobol_out.raw


# --------------------------------------------------------------------------
# Availability date: DATECNV "B" business-day shift
# --------------------------------------------------------------------------
def test_availability_date_shifts_off_a_weekend():
    """202306 -> 2023-07-15 is a Saturday; the COBOL used 2023-07-17."""
    assert availability_date("202306") == 20230717


def test_availability_date_shifts_off_the_holiday_table():
    """202303 -> 2023-04-15 is a Saturday, 04-16 is in HTAB, so the shift
    runs on to 2023-04-17."""
    assert availability_date("202303") == 20230417
    _, _, res = result_for(SHIPPED, "850001147")
    assert res.report_line.rstrip() == (
        "OVPINT  850001147 01 202303  O802  "
        "OVERPAYMENT INTEREST ALLOW      27626.68 1186    6283.75"
    )


def test_december_tax_period_rolls_availability_into_the_next_year():
    assert availability_date("202212") == 20230116
    _, _, res = result_for(SHIPPED, "450001217")
    assert res.report_line.rstrip() == (
        "OVPINT  450001217 02 202212  O802  "
        "OVERPAYMENT INTEREST ALLOW      95545.56 1277   23399.50"
    )


def test_availability_date_in_a_non_leap_century_year():
    """209912 -> 2100-01-15; 2100 is divisible by 100 but not 400."""
    assert availability_date("209912") == 21000115


def test_availability_date_in_a_leap_century_year():
    """199912 -> 2000-01-15 is a Saturday, so the shift lands on 01-17."""
    assert availability_date("199912") == 20000117


# --------------------------------------------------------------------------
# Defects reproduced on purpose
# --------------------------------------------------------------------------
def test_future_availability_date_reports_a_negative_age_as_positive():
    """WNDY goes negative when the refund is not yet available, but OR-DAYS
    is PIC ZZZ9, so the sign is dropped and the module is reported under the
    45-day rule with a plausible-looking day count."""
    _, _, res = result_for(SYNTHETIC, "990000003")
    assert res.report_line.rstrip() == (
        "OVPINT  990000003 01 202612  O801  "
        "45 DAY RULE - NO INTEREST        2500.75  153       0.00"
    )


def test_day_count_over_four_digits_loses_its_high_order_digits():
    """209912 is 26,816 days before the cycle date; OR-DAYS shows 6816."""
    _, _, res = result_for(SYNTHETIC, "990000001")
    assert res.report_line.rstrip() == (
        "OVPINT  990000001 01 209912  O801  "
        "45 DAY RULE - NO INTEREST        1000.00 6816       0.00"
    )


def test_overpayment_over_nine_digits_loses_its_high_order_digits():
    """WOVP is PIC S9(11)V99 but OR-OVP is PIC ZZZZZZZZ9.99, so an
    overpayment of 99,999,999,999.99 prints as 999,999,999.99."""
    _, _, res = result_for(SYNTHETIC, "990000004")
    assert "999999999.99" in res.report_line


def test_interest_over_nine_digits_wraps_in_the_module_record():
    """The true interest is 50,802,739,726.02; BMF-INT is PIC S9(9)V99 and
    keeps 802739726.02, and OR-INT is narrower still and prints
    2739726.02."""
    _, cobol_out, res = result_for(SYNTHETIC, "990000004")
    assert res.record.interest == Decimal("802739726.02") == cobol_out.interest
    assert res.report_line.rstrip().endswith("2649 2739726.02")


@pytest.mark.parametrize("ein", sorted(SHIPPED) + sorted(SYNTHETIC))
def test_thirty_day_floor_branch_is_unreachable(ein):
    """WNDY > 45 is already checked, so 'SUBTRACT 30 ... IF WNDY NOT >
    ZERO' can never fire.  No fixture reaches it, and none can."""
    pool = SHIPPED if ein in SHIPPED else SYNTHETIC
    record, _, res = result_for(pool, ein)
    if res.interest_counted:
        assert int(res.report_line.split()[-2]) > 15
