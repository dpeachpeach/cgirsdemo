"""Per-branch characterizations of FTDCALC as it behaves today.

Expected values are read from, or quoted from, the COBOL captures in
fixtures/; nothing here is derived from IRM 20.1.4 or from the rate table in
the program's comments.
"""

from decimal import Decimal

from helpers import amount_field, code_field, delinquency_field, lines_for, pftd, tier_field


def test_tier_1_rate_applies_below_six_days_late(shipped):
    """200001329, deposit three days late: 3,605.00 x 0.02 = 72.10 in the capture."""
    line = [
        item for item in lines_for(shipped.report, "20000132901202312") if "  3 " in item
    ][0]
    assert tier_field(line) == "1"
    assert amount_field(line) == "72.10"
    assert line in shipped.run().report


def test_tier_2_rate_applies_between_six_and_fifteen_days_late(shipped):
    line = lines_for(shipped.run().report, "12000111201202403")[0]
    assert (delinquency_field(line), tier_field(line), amount_field(line)) == (
        "8",
        "2",
        "4997.33",
    )
    assert line in shipped.report


def test_tier_3_rate_applies_from_sixteen_days_late(shipped):
    line = lines_for(shipped.run().report, "27000122401202309")[0]
    assert (delinquency_field(line), tier_field(line), amount_field(line)) == (
        "40",
        "3",
        "22782.20",
    )
    assert line in shipped.report


def test_tier_4_is_undocumented_and_triggered_by_x_in_w8_position_three(shipped):
    """The comment header claims 2/5/10 pct; BMF-W8(3:1)='X' silently adds a 15 pct tier."""
    line = lines_for(shipped.run().report, "12000111201202403")[1]
    assert (delinquency_field(line), tier_field(line), amount_field(line)) == (
        "20",
        "4",
        "14991.98",
    )
    assert line in shipped.report


def test_freeze_bypass_zeroes_the_accrual_and_writes_f403(shipped):
    codes = [code_field(item) for item in lines_for(shipped.report, "91000118901202409")]
    assert codes == ["F403"]
    assert pftd(shipped.run().modout, "91000118901202409") == Decimal("0.00")


def test_de_minimis_assessment_below_1000_writes_f402_and_zeroes_the_accrual(shipped):
    codes = [code_field(item) for item in lines_for(shipped.report, "20000100701202606")]
    assert codes == ["F402", "F403"]
    assert pftd(shipped.run().modout, "20000100701202606") == Decimal("0.00")


def test_deferral_window_credit_is_half_the_assessment(synthetic):
    """202006 module, assessment 50,000.00: the capture reports a 25,000.00 credit."""
    lines = lines_for(synthetic.run().report, "99000100101202006")
    assert [code_field(item) for item in lines] == ["F401", "F404"]
    assert amount_field(lines[1]) == "25000.00"
    assert lines == lines_for(synthetic.report, "99000100101202006")


def test_deferral_credit_larger_than_the_accrual_floors_the_penalty_at_zero(synthetic):
    assert pftd(synthetic.run().modout, "99000100101202006") == Decimal("0.00")
    assert pftd(synthetic.modout, "99000100101202006") == Decimal("0.00")


def test_deferral_credit_smaller_than_the_accrual_leaves_the_remainder(synthetic):
    assert pftd(synthetic.run().modout, "99000100201202009") == Decimal("9000.00")


def test_module_with_no_matching_transactions_produces_no_report_line(synthetic):
    assert lines_for(synthetic.run().report, "99000100401202306") == []
    assert pftd(synthetic.run().modout, "99000100401202306") == Decimal("0.00")


def test_penalty_is_carried_into_bmf_pftd_when_positive(shipped):
    assert pftd(shipped.run().modout, "12000111201202403") == Decimal("19989.31")
    assert pftd(shipped.modout, "12000111201202403") == Decimal("19989.31")
