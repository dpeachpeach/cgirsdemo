"""Branch-level characterization of FTDCALC as it behaves today.

Every expectation here was captured from a run of src/FTDCALC.cbl.  Tests whose
names say a behaviour is wrong assert it anyway: the defect is the specification
until someone decides otherwise.
"""

from decimal import Decimal


def _field(line):
    """Split a report line on the FRPT picture boundaries."""
    return {
        "ein": line[9:18],
        "mft": line[19:21],
        "txpd": line[22:28],
        "code": line[30:34],
        "text": line[36:62].rstrip(),
        "delinquency": line[64:69],
        "tier": line[70],
        "amount": line[72:83],
    }


def _both(golden, ein, code=None):
    """Assert the port and the COBOL agree, and return the COBOL lines."""
    cobol = golden.cobol_lines(ein, code)
    assert golden.python_lines(ein, code) == cobol
    return [_field(line) for line in cobol]


# --- tier structure -------------------------------------------------------


def test_tier_one_applies_two_percent_under_six_days_late(shipped):
    line = _both(shipped, "450001266", "F401")[0]
    assert line["delinquency"].strip() == "3"
    assert line["tier"] == "1"
    assert line["amount"].strip() == "3260.80"


def test_tier_two_applies_five_percent_from_six_through_fifteen_days(shipped):
    line = _both(shipped, "830001238", "F401")[0]
    assert line["delinquency"].strip() == "8"
    assert line["tier"] == "2"


def test_tier_three_applies_ten_percent_past_fifteen_days(shipped):
    lines = _both(shipped, "270001224", "F401")
    assert [line["tier"] for line in lines] == ["3"]
    assert lines[0]["amount"].strip() == "22782.20"


def test_tier_four_fifteen_percent_is_driven_by_w8_column_three_not_the_irm(shipped):
    """The in-line rate comment documents 2/5/10 only; the fourth tier fires
    whenever BMF-W8(3:1) is 'X' and the deposit is more than fifteen days late."""
    module = shipped.cobol_module("980001084")
    assert module.w8[2] == "X"
    lines = _both(shipped, "980001084", "F401")
    assert [line["tier"] for line in lines] == ["2", "4"]
    assert lines[1]["amount"].strip() == "93.54"


def test_tier_four_does_not_apply_at_fifteen_days_or_less(shipped):
    """Same module, the 8-day deposit stays on the tier 2 rate."""
    line = _both(shipped, "980001084", "F401")[0]
    assert line["tier"] == "2"
    assert line["amount"].strip() == "31.18"


# --- due date derivation --------------------------------------------------


def test_due_date_is_the_fifteenth_of_the_month_after_the_tax_period(shipped):
    line = _both(shipped, "940001203", "F401")[0]
    assert line["delinquency"].strip() == "8"


def test_sic_two_moves_the_due_date_to_january_thirty_first_of_the_next_year(shipped):
    """SIC 2 overwrites the month/day already derived and adds a further year,
    so a 202309 period is measured from 2024-01-31."""
    module = shipped.cobol_module("270001224")
    assert module.sic == "2"
    line = _both(shipped, "270001224", "F401")[0]
    assert line["delinquency"].strip() == "40"


def test_sic_one_moves_the_due_date_to_the_third_of_the_month(shipped):
    module = shipped.cobol_module("810001091")
    assert module.sic == "1"
    line = _both(shipped, "810001091", "F401")[0]
    assert line["delinquency"].strip() == "3"


# --- bypass, de minimis, posting -----------------------------------------


def test_freeze_a_bypasses_the_penalty_and_zeroes_the_accumulator(shipped):
    module = shipped.cobol_module("120001322")
    assert module.frz_a == "A"
    lines = _both(shipped, "120001322")
    assert [line["code"] for line in lines] == ["F403"]
    assert shipped.cobol_module("120001322").pftd == Decimal("0.00")


def test_freeze_s_bypasses_the_penalty_and_zeroes_the_accumulator(shipped):
    module = shipped.cobol_module("950001280")
    assert module.frz_s == "S"
    assert [line["code"] for line in _both(shipped, "950001280")] == ["F403"]
    assert shipped.cobol_module("950001280").pftd == Decimal("0.00")


def test_de_minimis_assessment_under_one_thousand_suppresses_the_penalty(shipped):
    module = shipped.cobol_module("940001161")
    assert module.assd < 1000
    assert [line["code"] for line in _both(shipped, "940001161")] == ["F402"]
    assert shipped.cobol_module("940001161").pftd == Decimal("0.00")


def test_de_minimis_and_freeze_both_report_when_both_apply(shipped):
    assert [line["code"] for line in _both(shipped, "200001007")] == ["F402", "F403"]


def test_penalty_is_posted_to_pftd_only_when_the_accumulator_is_positive(shipped):
    assert shipped.cobol_module("200001014").pftd == Decimal("26700.99")
    assert shipped.cobol_module("200001210").pftd == Decimal("0.00")


def test_zero_dollar_deposit_still_writes_a_late_deposit_line(shipped):
    """TRN-AMT of zero yields a 0.00 penalty and a report line anyway."""
    lines = _both(shipped, "200001210", "F401")
    assert [line["amount"].strip() for line in lines] == ["0.00", "0.00"]


def test_only_transaction_code_650_counts_as_a_deposit(shipped):
    """The module carries TC 150 and TC 976/977 transactions; none of them
    produce a delinquency line."""
    assert [line["code"] for line in _both(shipped, "940001203")] == ["F401"]


# --- synthetic-input branches --------------------------------------------


def test_deferral_window_subtracts_half_the_assessment_from_the_penalty(synthetic):
    """A 202003-202012 period has 50% of BMF-ASSD subtracted from the FTD
    penalty, which is an offset of tax against penalty; the comment says no
    current period qualifies, but the window is still live in the code."""
    lines = _both(synthetic, "990000001")
    assert [line["code"] for line in lines] == ["F401", "F404"]
    assert lines[0]["amount"].strip() == "100.00"
    assert lines[1]["amount"].strip() == "10000.00"
    assert synthetic.cobol_module("990000001").pftd == Decimal("0.00")


def test_deferral_floors_the_accumulator_at_zero_never_negative(synthetic):
    assert synthetic.cobol_module("990000001").pftd == Decimal("0.00")
    assert synthetic.python_module("990000001").pftd == Decimal("0.00")


def test_deferral_equal_to_the_penalty_leaves_exactly_zero_posted(synthetic):
    lines = _both(synthetic, "990000002")
    assert [line["amount"].strip() for line in lines] == ["500.00", "500.00"]
    assert synthetic.cobol_module("990000002").pftd == Decimal("0.00")


def test_zero_assessment_in_the_deferral_window_writes_no_deferral_line(synthetic):
    """WDFR of zero skips the F404 line entirely, so a zero-assessment module in
    the window is indistinguishable from one outside it."""
    assert [line["code"] for line in _both(synthetic, "990000003")] == ["F402"]


def test_impossible_julian_deposit_date_is_treated_as_on_time(synthetic):
    """DATCNV returns rc 8 for julian day 400; FTDCALC moves zero to DL and the
    deposit escapes the penalty instead of being rejected."""
    assert _both(synthetic, "990000004") == []
    assert synthetic.cobol_module("990000004").pftd == Decimal("0.00")


def test_delinquency_over_9999_days_loses_its_high_order_digit_in_the_report(synthetic):
    """DL is S9(5) but FR-DL is PIC ZZZ9-, so a 27978-day delinquency prints as
    7978.  The penalty itself is unaffected."""
    line = _both(synthetic, "990000005", "F401")[0]
    assert line["delinquency"].strip() == "7978"
    assert line["tier"] == "3"
    assert synthetic.cobol_module("990000005").pftd == Decimal("100.00")


def test_deposit_before_the_due_date_produces_no_penalty(synthetic):
    assert _both(synthetic, "990000006") == []


def test_negative_packed_deposit_reports_a_zero_penalty_and_ignores_penacc_rc(synthetic):
    """PENACC sets rc 8 and leaves the amount at zero for a negative base;
    FTDCALC never inspects PA-RC, so the deposit is reported as a late deposit
    with a 0.00 penalty."""
    line = _both(synthetic, "990000007", "F401")[0]
    assert line["amount"].strip() == "0.00"
    assert line["delinquency"].strip() == "104"
    assert synthetic.cobol_module("990000007").pftd == Decimal("0.00")


def test_module_with_no_transactions_reports_nothing(synthetic):
    assert _both(synthetic, "990000008") == []
    assert synthetic.cobol_module("990000008").pftd == Decimal("0.00")


def test_penalty_rounds_half_up_at_each_rate(synthetic):
    """0.02 / 0.05 / 0.10 of bases landing on a half cent round away from zero,
    matching COMPUTE PA-AMT ROUNDED in the PENACC shim."""
    lines = _both(synthetic, "990000009", "F401")
    assert [line["amount"].strip() for line in lines] == ["20.01", "5.01", "100.01"]
    assert synthetic.cobol_module("990000009").pftd == Decimal("125.03")


def test_penalty_over_the_pa_amt_capacity_silently_becomes_zero(synthetic):
    """A 99,999,999,999.99 deposit at 10% rounds to 10,000,000,000.00, which
    does not fit PA-AMT PIC S9(9)V99; the high-order digits are dropped and the
    taxpayer is charged nothing."""
    line = _both(synthetic, "990000010", "F401")[0]
    assert line["amount"].strip() == "0.00"
    assert synthetic.cobol_module("990000010").pftd == Decimal("0.00")


def test_transaction_below_the_module_key_is_silently_skipped(synthetic):
    """An orphan deposit for EIN 000000001 is consumed by the pre-loop skip and
    never appears anywhere in the output."""
    assert synthetic.cobol_lines("000000001") == []
    assert synthetic.python_lines("000000001") == []
    assert synthetic.cobol_counters["read"] == 62


def test_maximum_delinquency_is_computed_and_never_stored(synthetic):
    """PW-DLQ tracks the worst delinquency in the module and is discarded when
    3000-COMP returns; nothing in the record or the report carries it."""
    module = synthetic.cobol_module("990000009")
    assert module.pftd == Decimal("125.03")
    assert synthetic.python_module("990000009").to_bytes() == module.to_bytes()
