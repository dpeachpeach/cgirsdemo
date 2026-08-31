"""Characterization tests for the OFFSET port.

Every expected value in this file was captured from GnuCOBOL 3.1.2 running
src/OFFSET.cbl (step 090) against the fixtures in ../fixtures.  Where the COBOL
behaves defectively the test asserts the defect; the test name says so.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))

import offset  # noqa: E402

SCENARIOS = ["base", "s1", "s2", "s3", "s4"]


def run_scenario(tmp_path, name):
    modout = tmp_path / "MODOFF.dat"
    rptout = tmp_path / "OFFSET.rpt"
    counters = offset.run(
        FIXTURES / "MODINT.dat",
        FIXTURES / ("DEBTS_%s.txt" % name),
        modout,
        rptout,
    )
    return counters, modout.read_bytes(), rptout.read_text().splitlines()


def expected_report(name):
    return (FIXTURES / ("expected_%s.rpt" % name)).read_text().splitlines()


def expected_counters(name):
    return (FIXTURES / ("expected_%s.counters.txt" % name)).read_text().splitlines()


@pytest.mark.parametrize("name", SCENARIOS)
def test_report_matches_cobol_golden(tmp_path, name):
    _, _, report = run_scenario(tmp_path, name)
    assert report == expected_report(name)


@pytest.mark.parametrize("name", SCENARIOS)
def test_display_counters_match_cobol_golden(tmp_path, name):
    counters, _, _ = run_scenario(tmp_path, name)
    assert counters == expected_counters(name)


@pytest.mark.parametrize("name", SCENARIOS)
def test_module_output_is_byte_identical_to_input(tmp_path, name):
    """OFFSET writes MODOFF.dat unchanged: applied offsets are never posted."""
    _, modout, _ = run_scenario(tmp_path, name)
    assert modout == (FIXTURES / "expected_MODOFF.dat").read_bytes()
    assert modout == (FIXTURES / "MODINT.dat").read_bytes()


def test_debt_matched_on_ein_and_source_only_ignoring_mft_and_tax_period(tmp_path):
    """450001217's MFT 02/202212 module absorbs its MFT 30/202112 debt too."""
    debt_file = (FIXTURES / "DEBTS_base.txt").read_text().splitlines()
    assert "450001217BM3020211200000028289932024046" in debt_file
    _, _, report = run_scenario(tmp_path, "base")
    lines = [ln for ln in report if ln.startswith("OFFSET  450001217")]
    assert lines == [
        "OFFSET  450001217 02 202212  G902  OFFSET APPLIED            BM      8645.50    110299.56",
        "OFFSET  450001217 02 202212  G902  OFFSET APPLIED            BM     20528.83     89770.73",
        "OFFSET  450001217 02 202212  G902  OFFSET APPLIED            BM     28289.93     61480.80",
    ]


def test_source_priority_is_bmf_then_imf_then_dmf(tmp_path):
    _, _, report = run_scenario(tmp_path, "base")
    sources = [ln[61:63] for ln in report if "G902" in ln and ln.startswith("OFFSET  930001357")]
    assert sources == ["BM", "IM", "DM"]


def test_partial_offset_leaves_debt_open_without_recording_the_shortfall(tmp_path):
    """930001357's DM debt of 35821.00 gets 26736.94; the shortfall is unreported."""
    debt_file = (FIXTURES / "DEBTS_base.txt").read_text().splitlines()
    assert "930001357DM0120211200000035821002024228" in debt_file
    _, _, report = run_scenario(tmp_path, "base")
    dm = [ln for ln in report if ln.startswith("OFFSET  930001357") and ln[61:63] == "DM"]
    assert dm == [
        "OFFSET  930001357 01 202306  G902  OFFSET APPLIED            DM     26736.94         0.00"
    ]


def test_frozen_module_suppresses_offset_and_reports_zero_amount(tmp_path):
    _, _, report = run_scenario(tmp_path, "base")
    frozen = [ln for ln in report if "G901" in ln]
    assert frozen == [
        "OFFSET  200001007 01 202606  G901  OFFSET FROZEN                        0.00       697.52"
    ]


def test_debt_table_silently_drops_records_past_five_hundred(tmp_path):
    """DEBTS_s3.txt holds 510 records; WNDB caps at 500 with no reject report."""
    counters, _, report = run_scenario(tmp_path, "s3")
    assert counters[0] == "OFFSET  DEBTS   +00500"
    assert report == expected_report("base")


def test_exhausted_debt_balance_is_rescanned_on_every_module(tmp_path):
    """A zero-balance debt row stays in the table and is skipped, not removed."""
    counters, _, report = run_scenario(tmp_path, "s1")
    assert counters == expected_counters("s1")
    assert report == expected_report("base")


def test_scan_continues_after_available_credit_reaches_zero(tmp_path):
    """A second DM debt for 930001357 is skipped once available hits zero."""
    counters, _, report = run_scenario(tmp_path, "s2")
    assert counters[3] == "OFFSET  APPLIED 000012"
    assert report == expected_report("base")


def test_empty_debt_file_applies_nothing_but_still_reports_the_freeze(tmp_path):
    counters, _, report = run_scenario(tmp_path, "s4")
    assert counters[0] == "OFFSET  DEBTS   +00000"
    assert counters[3] == "OFFSET  APPLIED 000000"
    assert report == expected_report("s4")


def test_available_credit_of_exactly_zero_is_not_offset(tmp_path):
    """WAVL NOT > ZERO covers the equal-to-zero case: seven fixtures hit it."""
    modules = offset.read_modules(FIXTURES / "MODINT.dat")
    zero = [
        m for m in modules
        if m.dep + m.crd + m.interest - (m.assd + m.pftd + m.pftf + m.pftp) == 0
    ]
    assert len(zero) == 7
    _, _, report = run_scenario(tmp_path, "base")
    for module in zero:
        assert not [ln for ln in report if ln.startswith("OFFSET  " + module.ein)]


def test_packed_decimal_fields_decode_with_c_sign_nibble():
    modules = offset.read_modules(FIXTURES / "MODINT.dat")
    first = modules[0]
    assert first.ein == "100001077"
    assert first.assd == Decimal("391753.23")
    assert first.dep == Decimal("444753.48")
    assert first.interest == Decimal("11130.05")
    assert offset.pack_decimal(first.assd, 13, 2) == first.raw[78:85]


def test_report_amount_editing_truncates_above_nine_integer_digits():
    """PIC ZZZZZZZZ9.99 keeps the low nine integer digits of an S9(11)V99 move."""
    assert offset._edit_amount(Decimal("15028.60")) == "    15028.60"
    assert offset._edit_amount(Decimal("0")) == "        0.00"
    assert offset._edit_amount(Decimal("1234567890.12")) == "234567890.12"
