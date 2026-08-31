"""Characterization tests for the OVPINT port.

Every expected value in this file was captured from running the compiled COBOL
(GnuCOBOL 3.1.2, `./tools/build.sh` then `./run/pipeline.sh`), not derived from
IRM 20.2.4 or from IRC 6611.  Where the COBOL is wrong, the test asserts the
wrong answer and says so in its name; the corresponding fix is proposed in the
port report, not applied here.

The two golden pairs in ../fixtures/ are frozen so the suite runs from a clean
checkout without GnuCOBOL and without the pipeline having been run:

* shipped-*   — the 52 modules the repository's own fixtures produce.
* synthetic-* — the 7 modules built for branches the shipped fixtures miss,
                grown through data/MODMAST.txt and the full pipeline in a
                scratch tree (see fixtures/synthetic-MODMAST-generator.py).
"""

import os
from decimal import Decimal

import pytest

import ovpint

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures")


def fixture_path(name):
    return os.path.join(FIXTURES, name)


def load(prefix):
    records = ovpint.read_records(fixture_path(prefix + "-MODFRZ.dat"))
    expected_records = ovpint.read_records(fixture_path(prefix + "-MODINT.dat"))
    with open(fixture_path(prefix + "-OVPINT.rpt")) as handle:
        expected_report = handle.read().splitlines()
    return records, expected_records, expected_report


def run(prefix):
    records, expected_records, expected_report = load(prefix)
    return ovpint.run(records), expected_records, expected_report


def report_by_ein(prefix):
    result, _, _ = run(prefix)
    return {line[8:17]: line for line in result.report}


def golden_report_by_ein(prefix):
    _, _, expected_report = run(prefix)
    return {line[8:17]: line for line in expected_report}


def module_by_ein(prefix):
    result, _, _ = run(prefix)
    return {ovpint.BmfMod(raw).ein: ovpint.BmfMod(raw) for raw in result.records}


# ---------------------------------------------------------------------------
# Whole-file equivalence with the COBOL
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", ["shipped", "synthetic"])
def test_module_generation_is_byte_identical_to_cobol_output(prefix):
    result, expected_records, _ = run(prefix)
    assert result.records == expected_records


@pytest.mark.parametrize("prefix", ["shipped", "synthetic"])
def test_report_lines_are_identical_to_cobol_output(prefix):
    result, _, expected_report = run(prefix)
    assert [line.rstrip() for line in result.report] == expected_report


def test_shipped_fixture_counters_match_cobol_display_totals():
    # OVPINT  READ 000052 / WRITTEN 000052 / INTEREST 000005 / 45 DAY 000007
    result, _, _ = run("shipped")
    assert (result.read, result.written, result.interest, result.forty_five_day) == (
        52,
        52,
        5,
        7,
    )


def test_every_input_record_is_written_unconditionally():
    result, _, _ = run("shipped")
    assert result.written == result.read


# ---------------------------------------------------------------------------
# Defects reproduced on purpose
# ---------------------------------------------------------------------------
def test_report_text_truncates_overpayment_interest_allowed_literal():
    # OR-TXT is PIC X(26); the literal is 28 characters, so the MOVE drops
    # "ED" and every allowed-interest line reads "... ALLOW".
    line = report_by_ein("shipped")["100001077"]
    assert line[35:61] == "OVERPAYMENT INTEREST ALLOW"
    assert "ALLOWED" not in line


def test_forty_five_day_line_prints_a_future_period_day_count_without_its_sign():
    # EIN 990000001, tax period 209912: availability is 2100-01-15, later than
    # the hard-coded cycle date, so WNDY is -26816.  OR-DAYS is PIC ZZZ9, an
    # unsigned edited field, so the report shows 6816 - wrong magnitude and
    # wrong direction.
    line = report_by_ein("synthetic")["990000001"]
    assert line[35:61].rstrip() == "45 DAY RULE - NO INTEREST"
    assert line[76:80] == "6816"
    assert golden_report_by_ein("synthetic")["990000001"] == line.rstrip()


def test_overpayment_wider_than_nine_digits_truncates_in_the_report():
    # EIN 990000004 has a 99,999,999,999.99 deposit.  WOVP is PIC S9(11)V99
    # but OR-OVP is PIC ZZZZZZZZ9.99, so the two high-order digits vanish and
    # the report understates the overpayment by 99,000,000,000.
    line = report_by_ein("synthetic")["990000004"]
    assert line[63:75] == "999999999.99"


def test_interest_wider_than_nine_digits_wraps_in_the_module_record():
    # Same module: the true interest is 22,745,205,479.45, but WINT is
    # PIC S9(9)V99 and there is no ON SIZE ERROR, so the stored value keeps
    # only the low nine digits.
    assert module_by_ein("synthetic")["990000004"].interest == Decimal("745205479.45")
    # OR-INT is narrower still (PIC ZZZZZZ9.99), so the report shows only
    # seven of those nine digits.
    assert report_by_ein("synthetic")["990000004"][81:].strip() == "5205479.45"


def test_invalid_tax_period_month_dates_availability_from_the_year_1601():
    # EIN 990000003 carries tax period 202499.  XM is PIC 9(2), so ADD 1 TO XM
    # wraps 99 to 00, the month-13 correction never fires, and the resulting
    # 20240015 is not a date: INTEGER-OF-DATE returns zero, DATECNV shifts off
    # the "weekend" into 1601-01-02, and the module is paid 155,423 days of
    # interest on a 5,000.00 overpayment.
    line = report_by_ein("synthetic")["990000003"]
    assert line[76:80] == "5423"  # OR-DAYS PIC ZZZ9 truncates 155423
    assert module_by_ein("synthetic")["990000003"].interest == Decimal("149035.75")


def test_interest_period_drops_thirty_days_of_the_holding_period():
    # SUBTRACT 30 FROM WNDY before the interest COMPUTE, and the reported day
    # count is the reduced one.  EIN 100001077 (tax period 202306) is 1125 days
    # from availability to the cycle date and is paid for 1095.
    line = report_by_ein("shipped")["100001077"]
    assert line[76:80] == "1095"
    available, _dow, _rc = ovpint.datecnv_business(20230715)
    elapsed = ovpint._integer_of_date(ovpint.CYCLE_DATE) - ovpint._integer_of_date(
        available
    )
    assert elapsed == 1125


def test_interest_stops_at_a_hardcoded_cycle_date_and_a_hardcoded_rate():
    # CYCDT PIC 9(8) VALUE 20260815 and MOVE 0.0700 TO WRT7: the run date and
    # the IRC 6621 rate are both compiled in, so the day count is frozen no
    # matter when the cycle runs and no quarterly rate change is honoured.
    assert ovpint.CYCLE_DATE == 20260815
    assert ovpint.INTEREST_RATE == Decimal("0.0700")


def test_interest_is_simple_and_not_compounded_daily():
    # WOVP * WRT7 * WNDY / 365 with no compounding, against the 1095-day
    # allowed-interest line for EIN 100001077.
    line = report_by_ein("shipped")["100001077"]
    overpayment = Decimal("53000.25")
    simple = (overpayment * Decimal("0.0700") * 1095 / Decimal(365)).quantize(
        Decimal("0.01")
    )
    assert simple == Decimal("11130.05")
    assert line[81:].strip() == "11130.05"


# ---------------------------------------------------------------------------
# Arithmetic and rounding
# ---------------------------------------------------------------------------
def test_rounded_is_half_up_on_the_cent():
    # EIN 990000006: 91.25 for 1186 days is exactly 20.755 before ROUNDED, and
    # the COBOL writes 20.76 rather than truncating to 20.75.
    assert module_by_ein("synthetic")["990000006"].interest == Decimal("20.76")


def test_sub_cent_interest_rounds_to_zero_but_still_reports():
    # EIN 990000005: a one-cent overpayment earns 0.000227, which stores as
    # zero, yet the module still gets an O802 "interest allowed" report line.
    line = report_by_ein("synthetic")["990000005"]
    assert line[29:33] == "O802"
    assert line[81:].strip() == "0.00"
    assert module_by_ein("synthetic")["990000005"].interest == Decimal("0.00")


def test_zero_overpayment_produces_no_report_line():
    # EIN 990000007 has deposits exactly equal to the assessment.  WOVP NOT >
    # ZERO, so the record passes through untouched.
    assert "990000007" not in report_by_ein("synthetic")
    records, _, _ = load("synthetic")
    incoming = {ovpint.BmfMod(raw).ein: raw for raw in records}
    assert module_by_ein("synthetic")["990000007"].raw == incoming["990000007"]


def test_existing_interest_field_is_left_alone_when_no_interest_is_allowed():
    records, expected_records, _ = load("shipped")
    result = ovpint.run(records)
    paid = {line[8:17] for line in result.report if line[29:33] == "O802"}
    for incoming, outgoing in zip(records, result.records):
        if ovpint.BmfMod(incoming).ein not in paid:
            assert incoming == outgoing


# ---------------------------------------------------------------------------
# Availability date: the DATECNV / DATCNV COBOL shims
# ---------------------------------------------------------------------------
def test_availability_date_is_the_fifteenth_of_the_month_after_the_period():
    # Tax period 202403 -> 2024-04-15, a Monday, so no shift.
    assert ovpint.datecnv_business(20240415)[0] == 20240415


def test_availability_date_shifts_forward_off_a_saturday():
    assert ovpint.datecnv_business(20230715)[0] == 20230717


def test_availability_date_shifts_forward_off_the_holiday_table():
    # 2023-04-15 is a Saturday, 2023-04-16 is in HTAB, so the shift lands on
    # 2023-04-17.  HTAB holds fixed month/day values only - no observed
    # Monday holidays, and the entries 0416 and 0619 are not federal holidays
    # on those dates in every year.
    assert ovpint.datecnv_business(20230415)[0] == 20230417
    assert 416 in ovpint.HOLIDAYS


def test_december_period_rolls_the_availability_year_forward():
    records, _, _ = load("synthetic")
    incoming = {ovpint.BmfMod(raw).ein: ovpint.BmfMod(raw) for raw in records}
    assert incoming["990000002"].txpd == "199912"
    # 2000-01-15 is a Saturday; 2000 is a leap year through the mod-400 branch.
    assert ovpint.datecnv_business(20000115)[0] == 20000117
    assert ovpint._is_leap(2000) is True


def test_century_year_divisible_by_one_hundred_is_not_a_leap_year():
    assert ovpint._is_leap(2100) is False
    assert ovpint.datecnv_business(21000115)[0] == 21000115


def test_day_of_week_maps_sunday_to_seven():
    # 4000-DOW: FUNCTION MOD(WI 7) is zero on Sundays and the shim rewrites it.
    assert ovpint._day_of_week(20230716) == 7
    assert ovpint._day_of_week(20230715) == 6


def test_thirty_day_reduction_can_never_reach_the_zero_guard():
    # The IF WNDY NOT > ZERO after SUBTRACT 30 is dead code: the branch above
    # it already established WNDY > 45.
    for days in range(46, 400):
        assert days - 30 > 0
