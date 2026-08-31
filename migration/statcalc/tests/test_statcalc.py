"""Characterization tests for the STATCALC port.

Every expected value in this file was captured from GnuCOBOL 3.1.2 running
src/STATCALC.cbl (with src/DATCNV.cbl as the called shim), not derived from
IRM 25.6.1. Fixtures under ../fixtures/ are the frozen golden pairs, so the
suite runs from a clean checkout without GnuCOBOL and without the pipeline.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))

from statcalc import REC_LEN, Statcalc, unpack_decimal  # noqa: E402

CASES = ["shipped", "synth", "empty"]


def run(case):
    engine = Statcalc()
    modstat, report, counters = engine.run((FIX / f"moddup_{case}.dat").read_bytes())
    return engine, modstat, report, counters


def golden(case):
    return (
        (FIX / f"modstat_{case}.dat").read_bytes(),
        (FIX / f"statcalc_{case}.rpt").read_text(),
        (FIX / f"counters_{case}.txt").read_text(),
    )


@pytest.mark.parametrize("case", CASES)
def test_module_file_matches_cobol_byte_for_byte(case):
    _, modstat, _, _ = run(case)
    assert modstat == golden(case)[0]


@pytest.mark.parametrize("case", CASES)
def test_report_matches_cobol_line_for_line(case):
    _, _, report, _ = run(case)
    assert report == golden(case)[1]


@pytest.mark.parametrize("case", CASES)
def test_display_counters_match_cobol(case):
    engine, _, _, _ = run(case)
    assert engine.counters_text() == golden(case)[2]


def test_empty_input_writes_no_records_and_no_report():
    engine, modstat, report, counters = run("empty")
    assert (modstat, report) == (b"", "")
    assert counters == {"READ": 0, "WRITTEN": 0, "6YR": 0, "SUSPEND": 0}


def test_six_year_counter_is_never_incremented():
    """R6 ("STATCALC 6YR") has no ADD anywhere in the program: the six-year
    ASED rule the header comment implies was never implemented."""
    for case in CASES:
        engine, _, _, _ = run(case)
        assert engine.counters()["6YR"] == 0


def records(data):
    return [data[i:i + REC_LEN] for i in range(0, len(data), REC_LEN)]


def statutes(rec):
    return (
        int(unpack_decimal(rec[66:70])),
        int(unpack_decimal(rec[70:74])),
        int(unpack_decimal(rec[74:78])),
    )


def find(case, ein, mft=None):
    _, modstat, _, _ = run(case)
    for rec in records(modstat):
        if rec[0:9].decode() == ein and (mft is None or rec[9:11].decode() == mft):
            return rec
    raise AssertionError(f"{ein} not in {case} output")


def test_mft_01_return_due_date_is_month_after_period_on_the_28th():
    # EIN 100001308, MFT 01, tax period 202309 -> due 2023-10-28 -> julian 2023301.
    assert statutes(find("shipped", "100001308")) == (2026301, 2026301, 2033301)


def test_mft_01_december_period_rolls_the_due_year_forward():
    # EIN 200001014 tax period 202312 -> due 2024-01-28 -> julian 2024028.
    # The rolled year (2024) is what SY+3 / SY+10 are computed from, so RSED
    # is 2027028 rather than 2026028.
    rec = find("shipped", "200001014")
    assert statutes(rec)[1:] == (2027028, 2034028)


def test_mft_02_return_due_date_is_four_months_later_on_the_15th():
    # EIN 850001252, MFT 02, tax period 202403 -> due 2024-07-15 -> julian 2024197.
    assert statutes(find("shipped", "850001252")) == (2027197, 2027197, 2034197)


def test_mft_02_september_or_later_period_rolls_the_due_year_forward():
    # EIN 450001217, MFT 02, tax period 202212 -> due 2023-04-15 -> julian 2023105.
    assert statutes(find("shipped", "450001217")) == (2026105, 2026105, 2033105)


def test_other_mft_uses_january_31_of_the_following_year():
    # EIN 100001077, MFT 10, tax period 202306 -> due 2024-01-31 -> julian 2024031.
    assert statutes(find("shipped", "100001077")) == (2027031, 2027031, 2034031)


def test_statute_code_07_sets_ased_to_the_9999365_sentinel():
    rec = find("shipped", "200001014")
    assert statutes(rec)[0] == 9999365


def test_statute_code_12_hardcodes_ased_day_105_ignoring_the_return_due_date():
    """Code 12 (Form 872 consent) computes SY+3 but then pins the julian day to
    105 instead of using the computed return due day."""
    # EIN 860001105, tax period 202406, due 2024-07-28 -> julian day 210.
    rec = find("shipped", "860001105")
    assert statutes(rec)[0] == 2027105
    assert statutes(rec)[1] == 2027210


def test_statute_code_other_than_07_or_12_leaves_ased_at_three_years():
    # EIN 100001119, W8 code 55, tax period 202606 -> due 2026-07-28 -> 2026209.
    assert statutes(find("shipped", "100001119"))[0] == 2029209


def test_rsed_two_year_deposit_rule_never_fires():
    """2400-RSED recomputes RSED from SY+2 only when (SY+2)*1000 > RSED, but
    RSED is already (SY+3)*1000 + day, so the comparison can never be true:
    RSED equals the three-year value for every record, deposits or not."""
    # Both modules are MFT 01, period 202312; 200001014 has deposits of
    # 178,006.60 and 200001210 has none, yet RSED is identical.
    with_deposits = statutes(find("shipped", "200001014"))[1]
    without_deposits = statutes(find("shipped", "200001210"))[1]
    assert with_deposits == without_deposits == 2027028


def test_v_freeze_suspends_csed_by_183_days():
    # EIN 910001273, tax period 202209 -> due 2022-10-28 -> julian 301;
    # CSED 2032301 + 183 = 2032484 -> rolls to 2033119.
    assert statutes(find("shipped", "910001273"))[2] == 2033119


def test_z_freeze_alone_also_suspends_csed():
    # EIN 200001329, tax period 202312 -> due 2024-01-28 -> julian 028;
    # 2034028 + 183 = 2034211, no roll because 211 <= 365.
    assert statutes(find("shipped", "200001329"))[2] == 2034211


def test_csed_suspension_rollover_subtracts_365_not_the_year_length():
    """The roll adds 1000 and subtracts 365 unconditionally, so a suspension
    crossing a leap year lands one day earlier than the calendar would."""
    # EIN 200001007, tax period 202606 -> julian 209; 2036209 + 183 = 2036392
    # -> 2037027 (a plain +183 calendar shift from 2036-07-28 is 2037-01-27).
    assert statutes(find("shipped", "200001007"))[2] == 2037027


def test_no_freeze_leaves_csed_at_ten_years():
    assert statutes(find("shipped", "100001308"))[2] == 2033301


def test_report_carries_the_previous_records_csed_on_ased_only_lines():
    """8000-RPT moves W7CS into SR-CSED, but 2350-SPCL calls it before
    2500-CSED has run for this record, so S302/S303 lines print the CSED of
    whichever module was processed before them."""
    _, _, report, _ = run("synth")
    lines = report.splitlines()
    s302 = [line for line in lines if "S302" in line][0]
    assert s302.startswith("STATCALC  990001004 01 202306  S302")
    # 2106088 is the CSED of the preceding record (EIN 990001003, period 209602).
    assert s302[-7:] == "2106088"
    s304 = [line for line in lines if "S304" in line][0]
    assert s304[-7:] == "2034027"


def test_fraud_and_bankruptcy_on_one_module_emit_two_report_lines():
    _, _, report, _ = run("synth")
    lines = [line for line in report.splitlines() if "990001004" in line]
    assert [line[31:35] for line in lines] == ["S302", "S304"]


def test_century_year_is_not_treated_as_a_leap_year():
    # Synthetic EIN 990001001, tax period 210002 -> due 2100-03-28.
    # 2100 is divisible by 4 and by 100 but not 400 -> julian 087, not 088.
    assert statutes(find("synth", "990001001"))[1] == 2103087


def test_year_divisible_by_400_is_a_leap_year():
    # Synthetic EIN 990001002, tax period 240002 -> due 2400-03-28 -> julian 088.
    assert statutes(find("synth", "990001002"))[1] == 2403088


def test_ordinary_leap_year_adds_the_february_day():
    # Synthetic EIN 990001003, tax period 209602 -> due 2096-03-28 -> julian 088.
    assert statutes(find("synth", "990001003"))[1] == 2099088


def test_statute_dates_are_written_as_unsigned_packed_decimal():
    _, modstat, _, _ = run("shipped")
    for rec in records(modstat):
        for start in (66, 70, 74):
            assert rec[start + 3] & 0x0F == 0x0F


def test_only_the_three_statute_fields_are_rewritten():
    _, modstat, _, _ = run("shipped")
    moddup = (FIX / "moddup_shipped.dat").read_bytes()
    for before, after in zip(records(moddup), records(modstat)):
        assert before[:66] == after[:66]
        assert before[78:] == after[78:]


def test_branch_coverage_of_the_shipped_and_synthetic_fixtures():
    """The union of both golden inputs must keep hitting every branch the port
    reaches; the two structurally unreachable ones stay out of the set."""
    reached = set()
    for case in CASES:
        engine, _, _, _ = run(case)
        reached |= engine.branches
    expected = {f"B{i:02d}" for i in range(1, 22)} - {"B15"}
    expected |= {"D01", "D05", "D06", "D07", "D08", "D09", "D10", "D11", "D12", "D13", "D14"}
    assert reached == expected
