"""Per-branch characterization of STATCALC as it behaves today.

Every expected value below was read out of the GnuCOBOL run captured in
`fixtures/`. Where the legacy behavior is a defect the test name says so; the
proposed fixes are catalogued in the port report and are deliberately NOT
applied here.
"""

import pytest

import statcalc as S
from helpers import Run, ased, csed, rsed


@pytest.fixture(scope="module")
def shipped():
    return Run("shipped")


@pytest.fixture(scope="module")
def synthetic():
    return Run("synthetic")


# ---------------------------------------------------------------- return due date


def test_mft_01_return_due_date_is_the_28th_of_the_month_after_the_period(shipped):
    # EIN 810001091, MFT 01, period 202306 -> due 2023-07-28 (day 209), ASED = period year + 3
    assert ased(shipped.by_ein("810001091")) == 2026209


def test_mft_01_december_period_rolls_into_january_of_the_next_year(shipped):
    # period 202312 -> month 13 -> 2024-01-28 (day 028), ASED year still period year + 3
    assert ased(shipped.by_ein("200001210")) == 2027028


def test_mft_02_return_due_date_is_the_15th_four_months_after_the_period(shipped):
    # EIN 850001252, period 202403 -> 2024-07-15 (day 197, leap year)
    assert ased(shipped.by_ein("850001252")) == 2027197


def test_mft_02_period_month_over_eight_rolls_into_the_next_year(shipped):
    # EIN 450001217, period 202212 -> month 16 -> 2023-04-15 (day 105)
    assert ased(shipped.by_ein("450001217")) == 2026105


def test_any_other_mft_uses_january_31_of_the_year_after_the_period(shipped):
    # MFT 10 ignores the period month entirely: 202306 and 202312 both give day 031
    assert ased(shipped.by_ein("100001077")) == 2027031
    assert ased(shipped.by_ein("840001042")) == 2027031


# ---------------------------------------------------------------- statute condition code


def test_statute_code_07_replaces_ased_with_the_9999365_sentinel(shipped):
    rec = shipped.by_ein("200001014")
    assert ased(rec) == 9999365
    assert rsed(rec) == 2027028  # RSED is computed independently and stays normal
    line = shipped.report_for("200001014")[0]
    assert "S302  FRAUD - ASED NOT LIMITED" in line


def test_statute_code_12_uses_hardcoded_day_105_and_ignores_the_872_consent_date(
    shipped,
):
    # W8 positions 4-8 carry the consent date; 2350-SPCL moves them into DCP-RSV,
    # which nothing reads, then hardcodes day 105 of period year + 3.
    for ein, expected in (("860001105", 2027105), ("930001357", 2026105),
                          ("980001021", 2028105)):
        assert ased(shipped.by_ein(ein)) == expected


def test_statute_code_05_is_documented_but_has_no_branch_and_changes_nothing(shipped):
    # The prologue claims "CODES 05/07/12 ONLY"; 05 falls through 2350-SPCL
    # untouched, so ASED is the ordinary three-year date and nothing is reported.
    assert ased(shipped.by_ein("810001091")) == 2026209
    assert shipped.report_for("810001091") == []


def test_blank_byte_in_the_statute_code_is_read_as_a_zero_digit(synthetic):
    # W8 = " 7X00000": MOVE of the two-byte slice into PIC 9(2) yields 07, so a
    # partially blank code silently triggers the fraud path.
    assert ased(synthetic.by_ein("990000004")) == 9999365
    assert "S302  FRAUD" in synthetic.report_for("990000004")[0]


def test_all_blank_statute_code_yields_no_special_condition(synthetic):
    assert ased(synthetic.by_ein("990000005")) == 2026209
    assert synthetic.report_for("990000005") == []


# ---------------------------------------------------------------- RSED


def test_rsed_two_year_deposit_rule_can_never_fire(shipped):
    # 2400-RSED compares (period year + 2) * 1000 against a value that already
    # carries (period year + 3) * 1000, so the deposit-based RSED is dead code and
    # RSED always equals the three-year date.
    deposits_seen = 0
    for i in range(len(shipped.modin) // 150):
        if shipped.inp(i).packed(S.F_DEP, 2) > 0:
            deposits_seen += 1
            # CSED is the same date ten years out, so RSED is still the three-year
            # date whenever no freeze moved CSED.
            frz = shipped.inp(i).text(S.F_FRZ)
            if frz[1] != "V" and frz[6] != "Z":
                assert csed(shipped.out(i)) - rsed(shipped.out(i)) == 7000
    assert deposits_seen == 47
    assert shipped.job.trace.hits.get("S14") == 47  # the deposit test fires
    assert shipped.job.trace.hits.get("S16") is None  # the branch under it never does


def test_rsed_ignores_deposits_entirely(shipped):
    # 200001210 has no deposits, 810001091 does; both get the plain three-year RSED.
    assert rsed(shipped.by_ein("200001210")) == 2027028
    assert rsed(shipped.by_ein("810001091")) == 2026209


# ---------------------------------------------------------------- CSED


def test_csed_is_ten_years_from_the_return_due_date(shipped):
    assert csed(shipped.by_ein("810001091")) == 2033209


def test_v_freeze_suspends_csed_by_183_days(shipped):
    # EIN 910001273, period 202209 -> due day 301, CSED 2032301 + 183 -> 2033119
    assert csed(shipped.by_ein("910001273")) == 2033119


def test_z_freeze_suspends_csed_by_183_days(shipped):
    assert csed(shipped.by_ein("200001329")) == 2034211


def test_both_v_and_z_freezes_suspend_only_once(shipped):
    # EIN 200001007 carries V and Z; the OR is evaluated once, so one 183-day shift.
    assert csed(shipped.by_ein("200001007")) == 2037027


def test_csed_suspension_year_carry_uses_365_days_even_in_leap_years(shipped):
    # 2026209 + 183 = 2026392 -> day > 365 -> +1000 -365 = 2027027. A 366-day
    # source year would need 366 subtracted; the constant is hardcoded.
    assert csed(shipped.by_ein("200001007")) == 2037027
    assert csed(shipped.by_ein("920001140")) == 2033106


def test_unfrozen_modules_keep_the_plain_ten_year_csed(shipped):
    assert csed(shipped.by_ein("200001210")) == 2034028


# ---------------------------------------------------------------- report line


def test_ased_report_line_prints_the_previous_records_csed(shipped):
    # 8000-RPT is performed from 2350-SPCL before 2500-CSED has run, and SR-CSED
    # is WORKING-STORAGE, so an S302/S303 line carries the CSED of whichever
    # record last reached 2500-CSED.
    lines = shipped.report_lines()
    fraud = lines[1]
    assert fraud[10:19] == "200001014"
    assert fraud[81:88] == "2037027"  # 200001007's CSED, printed one line earlier
    assert csed(shipped.by_ein("200001014")) == 2034028


def test_report_holds_only_special_condition_records(shipped):
    assert len(shipped.report_lines()) == 15
    assert shipped.job.r7 == 15


def test_report_lines_are_88_characters_after_trailing_blank_removal(shipped):
    assert {len(ln) for ln in shipped.report_lines()} == {88}


# ---------------------------------------------------------------- DATCNV shim


def test_century_year_2100_is_not_a_leap_year(synthetic):
    # period 210002, MFT 01 -> 2100-03-28 -> day 087
    assert ased(synthetic.by_ein("990000001")) == 2103087


def test_year_2400_is_a_leap_year(synthetic):
    # period 240002, MFT 01 -> 2400-03-28 -> day 088
    assert ased(synthetic.by_ein("990000002")) == 2403088


def test_period_month_99_truncates_to_zero_and_reuses_the_previous_julian_date(
    synthetic,
):
    # MFT 01 adds 1 to a PIC 9(2) month of 99, giving 00, which is not > 12, so no
    # year roll happens and DATCNV is handed month 00. DATCNV sets RC 8 and leaves
    # DCP-JUL alone; STATCALC never checks RC, so the day-of-year 088 belonging to
    # the preceding record (990000002) is reused.
    rec = synthetic.by_ein("990000003")
    assert ased(rec) == 2102088
    assert csed(rec) == 2109088
    assert synthetic.job.trace.hits.get("D4") == 1


# ---------------------------------------------------------------- counters


def test_six_year_statute_counter_is_never_incremented(shipped):
    # R6 is displayed as "STATCALC 6YR" but no path touches it: the IRC 6501(e)
    # six-year statute is simply not implemented.
    assert shipped.job.r6 == 0
    assert shipped.job.displays().splitlines()[2] == "STATCALC 6YR    000000"
