"""Characterization tests for the CAWRMTCH port.

Every expected value in this file was captured by running the GnuCOBOL build of
src/CAWRMTCH.cbl against the input pair stored beside it under fixtures/. The
COBOL is the specification: where it is wrong, the test asserts the wrong
answer and says so in its name.
"""

import pathlib
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import cawrmtch  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
CASES = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())


def run_case(name, tmp_path):
    case = FIXTURES / name
    report = tmp_path / "CAWRMTCH.rpt"
    counters = cawrmtch.run(str(case / "MODOFF.dat"), str(case / "CAWRW2.txt"),
                            str(report))
    return report.read_text(), counters


def golden(name):
    case = FIXTURES / name
    return (case / "CAWRMTCH.rpt").read_text(), (case / "CAWRMTCH.out").read_text()


@pytest.mark.parametrize("name", CASES)
def test_report_matches_cobol_capture(name, tmp_path):
    produced, _ = run_case(name, tmp_path)
    expected, _ = golden(name)
    assert produced == expected


@pytest.mark.parametrize("name", CASES)
def test_end_of_job_counters_match_cobol_capture(name, tmp_path):
    _, counters = run_case(name, tmp_path)
    _, expected = golden(name)
    assert counters.render() == expected


def test_shipped_pipeline_pair_reproduces_all_forty_nine_report_lines(tmp_path):
    produced, counters = run_case("shipped_pipeline", tmp_path)
    assert len(produced.splitlines()) == 49
    assert counters == cawrmtch.CawrCounters(45, 49, 27, 4, 18)


def test_shipped_fixtures_never_reach_the_941_only_disposition(tmp_path):
    produced, _ = run_case("shipped_pipeline", tmp_path)
    assert "C004" not in produced


def line_for(report, ein, year):
    matches = [ln for ln in report.splitlines()
               if ln[10:19] == ein and ln[20:24] == year]
    assert matches, f"no report line for {ein}/{year}"
    return matches


def test_no_w2_data_reports_c004_with_negative_difference(tmp_path):
    produced, counters = run_case("no_w2_data", tmp_path)
    line = line_for(produced, "100000001", "2023")[0]
    assert line[26:30] == "C004"
    assert line[32:56].rstrip() == "NO W2 DATA FROM SSA"
    assert line[58:70] == "        0.00"
    assert line[71:83] == "    50000.00"
    assert line[84:97] == "    50000.00-"
    assert counters.discrepancies == 1


def test_941_only_group_counts_as_a_discrepancy_not_as_a_w2_only(tmp_path):
    _, counters = run_case("empty_w2_file", tmp_path)
    assert counters == cawrmtch.CawrCounters(2, 0, 0, 0, 2)


def test_modules_other_than_mft_01_are_skipped_entirely(tmp_path):
    produced, counters = run_case("empty_module_file", tmp_path)
    assert counters.groups_941 == 0
    assert produced.splitlines()[0][26:30] == "C005"


def test_control_break_sums_every_mft_01_module_for_the_ein_and_year(tmp_path):
    produced, counters = run_case("control_break_multi_module", tmp_path)
    assert counters.groups_941 == 1
    line = produced.splitlines()[0]
    assert line[71:83] == "   100000.00"


def test_tolerance_boundary_is_inclusive_so_exactly_one_percent_is_in_balance(
        tmp_path):
    produced, _ = run_case("tolerance_exact_boundary", tmp_path)
    assert produced.splitlines()[0][26:30] == "C001"


def test_one_cent_beyond_tolerance_falls_out_on_either_side(tmp_path):
    produced, counters = run_case("tolerance_one_cent_over", tmp_path)
    codes = [ln[26:30] for ln in produced.splitlines()]
    assert codes == ["C002", "C003"]
    assert counters.discrepancies == 2


def test_tolerance_is_truncated_not_rounded_at_the_third_decimal(tmp_path):
    # 1% of 12345.67 is 123.4567; COMPUTE without ROUNDED stores 123.45, so a
    # difference of 123.46 is a discrepancy even though it rounds to the limit.
    produced, _ = run_case("tolerance_truncation", tmp_path)
    codes = [ln[26:30] for ln in produced.splitlines()]
    assert codes == ["C001", "C002"]


def test_tolerance_floor_of_one_hundred_dollars_applies_to_small_liabilities(
        tmp_path):
    produced, _ = run_case("tolerance_minimum_floor", tmp_path)
    codes = [ln[26:30] for ln in produced.splitlines()]
    assert codes == ["C001", "C002"]


def test_negative_liability_prints_without_a_sign_in_the_941_column(tmp_path):
    # LEGACY DEFECT: CR-941 is PIC ZZZZZZZZ9.99 with no sign position, so a
    # credit balance of -50000.00 is reported as a 50000.00 liability while the
    # difference column is computed from the true negative value.
    produced, _ = run_case("negative_liability", tmp_path)
    line = produced.splitlines()[0]
    assert line[71:83] == "    50000.00"
    assert line[84:96] == "    51000.00"
    assert line[26:30] == "C002"


def test_amounts_over_nine_digits_lose_their_high_order_digits_in_the_report(
        tmp_path):
    # LEGACY DEFECT: the amount columns hold nine integer digits but the fields
    # they are moved from hold eleven, so large accounts silently under-report.
    produced, _ = run_case("report_field_overflow", tmp_path)
    line = produced.splitlines()[0]
    assert line[58:70] == "765432109.99"
    assert line[71:83] == "345678901.99"
    assert line[84:96] == "419753208.00"


def test_liability_accumulator_wraps_instead_of_flagging_a_size_error(tmp_path):
    # LEGACY DEFECT: 3000-GRP has no ON SIZE ERROR, so two 60 billion dollar
    # modules accumulate to 20 billion and the account reports in balance.
    produced, counters = run_case("liability_accumulator_overflow", tmp_path)
    assert produced.splitlines()[0][26:30] == "C001"
    assert counters.matched == 1


def test_second_w2_for_the_same_key_is_reported_as_having_no_941_module(
        tmp_path):
    # The 941 group is consumed by the first W-2 record, so a duplicate SSA
    # filing for the same EIN and year falls out as C005 rather than as a
    # duplicate.
    produced, counters = run_case("duplicate_w2_same_key", tmp_path)
    codes = [ln[26:30] for ln in produced.splitlines()]
    assert codes == ["C001", "C005"]
    assert counters.w2_only == 1


def test_zero_liability_and_zero_withholding_are_in_balance(tmp_path):
    produced, _ = run_case("zero_both_sides", tmp_path)
    assert produced.splitlines()[0][26:30] == "C001"


def test_three_way_interleave_emits_every_disposition_in_key_order(tmp_path):
    produced, counters = run_case("three_way_interleave", tmp_path)
    codes = [ln[26:30] for ln in produced.splitlines()]
    assert codes == ["C004", "C005", "C001", "C004", "C003", "C005"]
    assert counters == cawrmtch.CawrCounters(4, 4, 1, 2, 3)


def test_match_key_is_ein_plus_tax_year_so_years_group_separately(tmp_path):
    produced, counters = run_case("same_ein_multiple_years", tmp_path)
    codes = [ln[26:30] for ln in produced.splitlines()]
    assert codes == ["C001", "C004", "C002"]
    assert counters.groups_941 == 3


def test_tax_period_month_is_ignored_so_all_quarters_collapse_into_one_group(
        tmp_path):
    produced, counters = run_case("txpd_month_ignored", tmp_path)
    assert counters.groups_941 == 1
    assert produced.splitlines()[0][71:83] == "     3000.00"


def test_short_w2_line_is_space_padded_to_forty_four_bytes(tmp_path):
    produced, counters = run_case("short_w2_line", tmp_path)
    assert counters.w2_records == 1
    assert produced.splitlines()[0][26:30] == "C001"


def test_report_lines_are_written_with_trailing_spaces_trimmed(tmp_path):
    produced, _ = run_case("shipped_pipeline", tmp_path)
    for line in produced.splitlines():
        assert not line.endswith(" ")
        assert len(line) in (96, 97)


def test_packed_decimal_sign_nibbles_decode_to_signed_values():
    assert cawrmtch.unpack_comp3(bytes.fromhex("0000039175323c"), 2) == \
        Decimal("391753.23")
    assert cawrmtch.unpack_comp3(bytes.fromhex("0000039175323d"), 2) == \
        Decimal("-391753.23")
    assert cawrmtch.unpack_comp3(bytes.fromhex("0000039175323f"), 2) == \
        Decimal("391753.23")


def test_s11v2_store_truncates_toward_zero_and_drops_overflow():
    assert cawrmtch.truncate_s11v2(Decimal("123.4567")) == Decimal("123.45")
    assert cawrmtch.truncate_s11v2(Decimal("-123.4567")) == Decimal("-123.45")
    assert cawrmtch.truncate_s11v2(Decimal("120000000000.00")) == \
        Decimal("20000000000.00")
