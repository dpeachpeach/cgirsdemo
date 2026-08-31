"""Defects of src/FTDCALC.cbl, reproduced deliberately by the port.

Each of these asserts behaviour that is wrong on its face.  It is asserted
because the COBOL does it and the migration must not silently change it; the
corresponding proposed fixes are listed in the port report and are NOT applied.
"""

from decimal import Decimal

from helpers import amount_field, code_field, delinquency_field, lines_for, pftd


def test_report_amount_over_eight_digits_loses_its_high_order_digit(synthetic):
    """FR-AMT is PIC ZZZZZZZ9.99: a 150,000,000.00 penalty prints as 50,000,000.00."""
    line = lines_for(synthetic.run().report, "99000100701202306")[0]
    assert amount_field(line) == "50000000.00"
    assert pftd(synthetic.run().modout, "99000100701202306") == Decimal("150000000.00")
    assert line in synthetic.report


def test_penalty_exceeding_pa_amt_capacity_silently_wraps_to_zero(synthetic):
    """PA-AMT is PIC S9(9)V99 and PENACC has no ON SIZE ERROR: 2,000,000,000.00 becomes 0."""
    line = lines_for(synthetic.run().report, "99000100801202306")[0]
    assert amount_field(line) == "0.00"
    assert pftd(synthetic.run().modout, "99000100801202306") == Decimal("0.00")
    assert line in synthetic.report


def test_delinquency_over_9999_days_is_truncated_in_the_report(synthetic):
    """FR-DL is PIC ZZZ9-: 27,763 days late prints as 7763, the tier is still correct."""
    line = lines_for(synthetic.run().report, "99000100601202306")[0]
    assert delinquency_field(line) == "7763"
    assert line in synthetic.report


def test_sic_2_december_period_due_date_lands_two_years_after_the_period(shipped):
    """The month rollover runs before the SIC 2 override, so both add a year.

    260001168 / 202212 has a deposit on julian 2023051 (2023-02-20).  The due
    date the program computes is 2024-01-31, so the deposit is early and no
    penalty is written; with a single year increment it would be 20 days late.
    """
    assert lines_for(shipped.report, "26000116801202212") == []
    assert lines_for(shipped.run().report, "26000116801202212") == []
    assert pftd(shipped.run().modout, "26000116801202212") == Decimal("0.00")


def test_zero_amount_deposit_still_writes_a_late_deposit_line(shipped):
    """Three 0.00 deposits for 200001210: two are late and each gets an F401 of 0.00."""
    lines = lines_for(shipped.run().report, "20000121001202312")
    assert [code_field(item) for item in lines] == ["F401", "F401"]
    assert {amount_field(item) for item in lines} == {"0.00"}
    assert lines == lines_for(shipped.report, "20000121001202312")


def test_unconvertible_deposit_date_is_treated_as_timely(synthetic):
    """DATCNV returns RC 8 for julian 2023400; the program moves ZERO to DL and moves on."""
    assert lines_for(synthetic.report, "99000100501202306") == []
    assert lines_for(synthetic.run().report, "99000100501202306") == []
    assert pftd(synthetic.run().modout, "99000100501202306") == Decimal("0.00")


def test_transactions_ahead_of_the_module_key_are_dropped_without_a_reject(synthetic):
    """990001004/209912 matches no module; nothing in the capture mentions it."""
    assert [line for line in synthetic.report if "209912" in line] == []
    assert [line for line in synthetic.run().report if "209912" in line] == []


def test_negative_deposit_amount_yields_a_zero_penalty_line_not_a_reject(
    synthetic_negative,
):
    """PENACC sets RC 8 and PA-AMT to zero; FTDCALC never looks at PA-RC."""
    line = lines_for(synthetic_negative.run().report, "99000100101202006")[0]
    assert (code_field(line), amount_field(line)) == ("F401", "0.00")
    assert line in synthetic_negative.report


def test_deferral_credit_is_reported_even_when_it_exceeds_the_accrual(
    synthetic_negative,
):
    """The F404 line shows the full 25,000.00 credit against an accrual of 0.00."""
    lines = lines_for(synthetic_negative.run().report, "99000100101202006")
    assert [code_field(item) for item in lines] == ["F401", "F404"]
    assert amount_field(lines[1]) == "25000.00"
    assert lines == lines_for(synthetic_negative.report, "99000100101202006")
