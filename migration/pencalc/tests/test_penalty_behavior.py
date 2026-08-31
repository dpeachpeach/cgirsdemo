"""Targeted characterization of individual PENCALC branches.

Every expected value here was captured from src/PENCALC.cbl compiled with
GnuCOBOL (shipped fixtures, or synthetic records added in a scratch tree and
frozen under fixtures/synthetic/). Several assertions record defects; those
tests are named for the defect, not for the intended rule.
"""

from decimal import Decimal

import pencalc


def test_ftf_intermediate_is_truncated_to_two_decimals_before_month_multiply(
    shipped,
):
    # WUPD 25010.87, 4 months late: COBOL computed FTF 5002.16 - FTP 500.21.
    # Multiplying first and truncating once gives 4501.96, one cent high.
    mod = shipped.module("260001168", "202212")
    assert mod.pftf == Decimal("4501.95")
    naive = pencalc.truncate(Decimal("25010.87") * Decimal("0.05") * 4, 2)
    assert naive - Decimal("500.21") == Decimal("4501.96")


def test_ftp_intermediate_is_truncated_to_three_decimals(shipped):
    mod = shipped.module("260001168", "202212")
    assert mod.pftp == Decimal("500.21")


def test_ftf_is_reduced_by_ftp_so_the_report_ftf_is_net(shipped):
    mod = shipped.module("260001168", "202212")
    assert mod.pftf + mod.pftp == Decimal("5002.16")


def test_minimum_penalty_uses_stale_hardcoded_485_amount(synthetic):
    # 991000006: WUPD 10000.00, 64 months late. Both 25% caps bind, the FTP
    # offset zeroes FTF, then the minimum-penalty branch reinstates 485.00.
    assert pencalc.MINIMUM_PENALTY == Decimal("485.00")
    mod = synthetic.module("991000006", "201812")
    assert mod.pftp == Decimal("2500.00")
    assert mod.pftf == Decimal("485.00") - Decimal("2500.00")


def test_minimum_penalty_subtracts_ftp_again_and_can_go_negative(synthetic):
    mod = synthetic.module("991000006", "201812")
    assert mod.pftf == Decimal("-2015.00")


def test_report_prints_negative_ftf_without_its_sign(synthetic):
    lines = synthetic.lines("991000006")
    assert len(lines) == 2
    assert lines[0].endswith("64    2015.00    2500.00")
    assert "-" not in lines[0]


def test_minimum_penalty_is_capped_by_the_unpaid_balance(shipped):
    # 920001315: WUPD 200.33 < 485.00, so the floor becomes the balance and
    # the FTP subtraction still applies: 200.33 - 13.01 = 187.32.
    mod = shipped.module("920001315", "202303")
    assert mod.pftp == Decimal("13.01")
    assert mod.pftf == Decimal("187.32")


def test_minimum_penalty_branch_emits_two_report_lines(shipped):
    lines = shipped.lines("920001315")
    assert [ln.split()[4] for ln in lines] == ["P502", "P501"]


def test_penalty_fields_wrap_when_the_computed_amount_overflows(synthetic):
    # 991000011: WUPD 99999999999.99 -> 25% cap 24999999999.99 does not fit
    # S9(9)V99; COBOL kept the low-order nine integer digits.
    mod = synthetic.module("991000011", "202312")
    assert mod.pftp == Decimal("999999999.99")
    assert mod.pftf == Decimal("-999999514.99")


def test_report_money_field_drops_high_order_digits(synthetic):
    # PIC ZZZZZZ9.99 holds seven integer positions, so 999999514.99 prints
    # as 9999514.99 with no overflow indication.
    lines = synthetic.lines("991000011")
    assert lines[0].endswith("4 9999514.99 9999999.99")


def test_module_with_no_transactions_gets_no_penalty(synthetic):
    mod = synthetic.module("991000002", "202312")
    assert (mod.pftf, mod.pftp) == (Decimal("0.00"), Decimal("0.00"))
    assert synthetic.lines("991000002") == []


def test_module_without_a_tc150_gets_no_penalty(synthetic):
    # Transactions exist for the module but none is TC 150, so D150 stays
    # zero and the months-late computation exits early.
    mod = synthetic.module("991000003", "202312")
    assert (mod.pftf, mod.pftp) == (Decimal("0.00"), Decimal("0.00"))


def test_return_filed_before_the_due_date_gets_no_penalty(synthetic):
    mod = synthetic.module("991000004", "202312")
    assert (mod.pftf, mod.pftp) == (Decimal("0.00"), Decimal("0.00"))


def test_part_month_late_counts_as_one_whole_month(synthetic):
    # 991000005 filed 25 days after the due date: one month, 5% of 1000.00.
    mod = synthetic.module("991000005", "202312")
    assert mod.pftf == Decimal("45.00")
    assert mod.pftp == Decimal("5.00")
    assert synthetic.lines("991000005")[0].split()[-3] == "1"


def test_ftp_truncates_to_zero_on_a_one_cent_balance(synthetic):
    # 991000007: WUPD 0.01, 10 months. FTP truncates to 0.00, so the FTP
    # offset never fires and the minimum branch floors FTF at the balance.
    mod = synthetic.module("991000007", "202306")
    assert mod.pftp == Decimal("0.00")
    assert mod.pftf == Decimal("0.01")


def test_negative_net_balance_is_floored_at_zero(synthetic):
    # 991000012: assessment 100.00, deposits 500.00.
    mod = synthetic.module("991000012", "202312")
    assert mod.assd - mod.dep - mod.crd == Decimal("-400.00")
    assert (mod.pftf, mod.pftp) == (Decimal("0.00"), Decimal("0.00"))


def test_invalid_julian_filing_date_is_treated_as_no_penalty(synthetic):
    # 991000008 carries Julian 2023366, which DATCNV rejects with RC 8 and
    # leaves the Gregorian date unchanged at zero; PENCALC ignores the RC.
    mod = synthetic.module("991000008", "202312")
    assert (mod.pftf, mod.pftp) == (Decimal("0.00"), Decimal("0.00"))


def test_orphan_transaction_below_the_module_key_is_skipped(synthetic):
    # A TC 150 for EIN 990999999 has no module; the following module is
    # still penalized normally.
    mod = synthetic.module("991000001", "202312")
    assert mod.pftf == Decimal("900.00")
    assert mod.pftp == Decimal("100.00")


def test_modules_after_the_last_transaction_get_no_penalty(synthetic):
    mod = synthetic.module("991000013", "202312")
    assert (mod.pftf, mod.pftp) == (Decimal("0.00"), Decimal("0.00"))


def test_untouched_module_bytes_are_copied_through(shipped):
    left = shipped.result.mod_out[:105]
    assert left == shipped.mod_in[:105]
    assert shipped.result.mod_out[117:150] == shipped.mod_in[117:150]
