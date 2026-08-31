"""Characterization tests for the OFFSET port.

Every expected value in this file was captured from an actual run of the
GnuCOBOL build of src/OFFSET.cbl (see fixtures/<scenario>/). Nothing here is
derived from the IRM or from the offset rule as documented.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))

import offset  # noqa: E402

SCENARIOS = [
    "s0_shipped",
    "s1_zero_balance_debt",
    "s2_second_debt_after_exhaustion",
    "s3_no_debts",
    "s4_table_overflow",
]


def cobol_run(scenario):
    return offset.run(FIXTURES / "MODINT.dat", FIXTURES / scenario / "DEBTS.txt")


def golden_report(scenario):
    text = (FIXTURES / scenario / "OFFSET.rpt").read_text(encoding="latin-1")
    return text.splitlines()


def golden_stdout(scenario):
    text = (FIXTURES / scenario / "stdout.txt").read_text(encoding="latin-1")
    return text.splitlines()


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_report_matches_cobol_line_for_line(scenario):
    assert cobol_run(scenario).report == golden_report(scenario)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_display_counters_match_cobol(scenario):
    assert cobol_run(scenario).counters() == golden_stdout(scenario)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_module_output_file_matches_cobol_byte_for_byte(scenario):
    golden = (FIXTURES / scenario / "MODOFF.dat").read_bytes()
    assert cobol_run(scenario).modules_out == golden


def test_module_record_is_written_through_unchanged_despite_offset():
    """The offset is reported but never subtracted from the module's credits.

    MODOFF.dat is byte-identical to MODINT.dat even for the twelve modules
    that had an offset applied; the downstream steps therefore still see the
    full overpayment. Reproduced deliberately (proposed fix logged, not
    applied).
    """
    result = cobol_run("s0_shipped")
    assert result.applied == 12
    assert result.modules_out == (FIXTURES / "MODINT.dat").read_bytes()


def test_frozen_module_reports_zero_amount_and_full_remaining():
    lines = [line for line in cobol_run("s0_shipped").report if "G901" in line]
    assert lines == [
        "OFFSET  200001007 01 202606  G901  OFFSET FROZEN                        "
        "0.00       697.52"
    ]


def test_debt_smaller_than_available_is_applied_in_full():
    line = cobol_run("s0_shipped").report[0]
    assert line == (
        "OFFSET  100001119 01 202606  G902  OFFSET APPLIED            DM     "
        "15028.60      8611.11"
    )


def test_debt_larger_than_available_is_capped_at_the_available_credit():
    lines = [line for line in cobol_run("s0_shipped").report if "930001357" in line]
    assert lines[-1] == (
        "OFFSET  930001357 01 202306  G902  OFFSET APPLIED            DM     "
        "26736.94         0.00"
    )


def test_sources_are_satisfied_in_bm_im_dm_order():
    lines = [line for line in cobol_run("s0_shipped").report if "930001357" in line]
    assert [line[61:63] for line in lines] == ["BM", "IM", "DM"]


def test_debts_beyond_the_five_hundredth_are_silently_dropped():
    """The table holds 500 entries; the 39 real debts sit past the cut."""
    result = cobol_run("s4_table_overflow")
    assert result.debts_loaded == 500
    assert result.applied == 0
    assert golden_stdout("s4_table_overflow")[0] == "OFFSET  DEBTS   +00500"


def test_zero_balance_debt_is_skipped_without_a_report_line():
    shipped = cobol_run("s0_shipped")
    with_zero = cobol_run("s1_zero_balance_debt")
    assert with_zero.debts_loaded == shipped.debts_loaded + 1
    assert with_zero.report == shipped.report


def test_debt_reached_after_credit_is_exhausted_is_left_untouched():
    shipped = cobol_run("s0_shipped")
    exhausted = cobol_run("s2_second_debt_after_exhaustion")
    assert exhausted.applied == shipped.applied
    assert exhausted.report == shipped.report


def test_empty_debt_file_still_reports_the_frozen_module():
    result = cobol_run("s3_no_debts")
    assert result.debts_loaded == 0
    assert result.applied == 0
    assert result.suppressed == 1
    assert len(result.report) == 1


def test_frozen_check_happens_before_any_debt_is_scanned():
    """A frozen module never consumes debt balances, even when they match."""
    result = cobol_run("s0_shipped")
    frozen_eins = [line[8:17] for line in result.report if "G901" in line]
    applied_eins = [line[8:17] for line in result.report if "G902" in line]
    assert set(frozen_eins).isdisjoint(applied_eins)


def test_available_credit_not_greater_than_zero_produces_no_report_line():
    modules = offset.read_modules(FIXTURES / "MODINT.dat")
    reported = {line[8:17] + line[18:20] + line[21:27]
                for line in cobol_run("s0_shipped").report}
    overdrawn = [m for m in modules
                 if m.dep + m.crd + m.interest
                 - (m.assd + m.pftd + m.pftf + m.pftp) <= 0]
    assert len(overdrawn) == 40
    for module in overdrawn:
        assert module.ein + module.mft + module.txpd not in reported


def test_comp3_round_trip_preserves_every_module_record():
    for module in offset.read_modules(FIXTURES / "MODINT.dat"):
        assert offset.encode_comp3(module.assd, 13, 2) == module.raw[78:85]
        assert offset.encode_comp3(module.dep, 13, 2) == module.raw[85:92]
        assert offset.encode_comp3(module.interest, 11, 2) == module.raw[117:123]


def test_edited_amount_field_truncates_to_nine_integer_digits():
    """PIC ZZZZZZZZ9.99 keeps only the low-order nine integer digits."""
    assert offset.edited_z9_99(Decimal("1234567890.12")) == "234567890.12"
    assert offset.edited_z9_99(Decimal("0")) == "        0.00"
