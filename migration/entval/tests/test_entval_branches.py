"""Branch-level characterization of ENTVAL.

Every expected value in this file is read out of a golden fixture that the
compiled COBOL produced (migration/entval/fixtures/), never derived from
IRM 3.13.2 or from the rule as documented in the comments.
"""

import pytest

import entval
from golden import golden_record, output_record, run_case

FIXTURES_MISSING_INPUT = "fixtures/does-not-exist.dat"


def field(record, fld):
    off, length = fld
    return record[off:off + length]


# ---------------------------------------------------------------- 1000-INIT


def test_missing_input_file_displays_file_status_35_and_returns_16():
    result = entval.run_file(FIXTURES_MISSING_INPUT)
    assert result.return_code == 16
    assert result.console == ["ENTVAL OPEN FAIL ENTIN 35"]
    assert result.records == []


# ----------------------------------------------------------------- 2200-PFX


def test_prefix_absent_from_the_1991_campus_table_reports_e101():
    result = run_case("synth_a")
    assert "ENTVAL  990000011  E101  PREFIX NOT IN CAMPUS TABLE" in result.report_text


def test_prefix_00_is_absent_from_the_table_and_reports_e101():
    result = run_case("synth_b")
    assert "ENTVAL  000000035  E101  PREFIX NOT IN CAMPUS TABLE" in result.report_text


def test_prefix_from_the_last_table_entry_is_accepted():
    result = run_case("synth_a")
    assert "440000012" not in result.report_text


def test_prefix_from_the_third_table_row_is_accepted():
    result = run_case("synth_b")
    assert "160000034" not in result.report_text


def test_e101_record_is_still_written_to_the_valid_output_file():
    result = run_case("synth_a")
    assert output_record(result, "990000011") == golden_record("synth_a", "990000011")


# ---------------------------------------------------------- 2300-NCTL/NAMCTL


def test_blank_name_is_not_derivable_and_leaves_the_stored_name_control():
    result = run_case("synth_a")
    assert (
        "ENTVAL  100000013  E102  NAME CONTROL NOT DERIVABLE                ABCD"
        in result.report_text
    )
    assert field(output_record(result, "100000013"), entval.F_NCTL) == "ABCD"


def test_name_consisting_only_of_the_article_the_is_not_derivable():
    result = run_case("synth_a")
    assert "100000014  E102" in result.report_text


def test_punctuation_only_name_is_not_derivable():
    result = run_case("synth_a")
    assert "100000015  E102" in result.report_text


def test_squeeze_drops_punctuation_before_taking_four_characters():
    result = run_case("synth_b")
    assert (
        "ENTVAL  100000033  E103  NAME CONTROL MISMATCH - CORRECTED         -ABC  ABCD"
        in result.report_text
    )
    assert field(output_record(result, "100000033"), entval.F_NCTL) == "ABCD"


def test_leading_blank_stops_the_article_drop_so_the_control_starts_with_the():
    result = run_case("synth_b")
    assert "100000031" not in result.report_text
    assert field(output_record(result, "100000031"), entval.F_NCTL) == "THEA"


def test_lower_case_article_is_dropped_because_the_name_is_upper_cased_first():
    result = run_case("synth_b")
    assert field(output_record(result, "100000032"), entval.F_NCTL) == "AVOC"


def test_only_one_leading_the_is_dropped():
    result = run_case("synth_b")
    assert field(output_record(result, "100000036"), entval.F_NCTL) == "THEA"


def test_extra_blanks_after_the_article_are_squeezed_out():
    result = run_case("synth_b")
    assert field(output_record(result, "100000039"), entval.F_NCTL) == "AVOC"


def test_derived_control_shorter_than_four_characters_is_blank_padded():
    result = run_case("synth_a")
    assert field(output_record(result, "100000025"), entval.F_NCTL) == "AB  "
    assert "100000025" not in result.report_text


def test_case_only_difference_counts_as_a_mismatch_and_is_corrected():
    result = run_case("synth_a")
    assert (
        "ENTVAL  100000027  E103  NAME CONTROL MISMATCH - CORRECTED         sisk  SISK"
        in result.report_text
    )


def test_blank_stored_name_control_is_reported_as_a_mismatch_not_as_missing():
    result = run_case("synth_b")
    assert (
        "ENTVAL  100000038  E103  NAME CONTROL MISMATCH - CORRECTED               OSPR"
        in result.report_text
    )


def test_name_control_corrections_are_counted_apart_from_errors():
    result = run_case("shipped")
    assert (result.error_count, result.nc_corrected_count) == (1, 10)


# ----------------------------------------------------------------- 2400-FRC


def test_ec_f_with_940_filing_requirement_reports_e104_and_blanks_the_indicator():
    result = run_case("synth_a")
    assert "ENTVAL  100000019  E104  EC F INCOMPATIBLE WITH 940 FRC" in result.report_text
    assert field(output_record(result, "100000019"), entval.F_I_940) == " "


def test_ec_f_without_the_940_filing_requirement_is_left_alone():
    result = run_case("synth_a")
    assert "100000020" not in result.report_text
    assert field(output_record(result, "100000020"), entval.F_I_941) == "1"


def test_940_filing_requirement_with_a_non_f_employment_code_is_left_alone():
    result = run_case("synth_a")
    assert "100000021" not in result.report_text
    assert field(output_record(result, "100000021"), entval.F_I_940) == "1"


def test_zero_fiscal_year_month_defaults_to_december_with_no_report_line():
    result = run_case("synth_a")
    assert field(output_record(result, "100000017"), entval.F_FYM) == "12"
    assert "100000017" not in result.report_text


@pytest.mark.parametrize(
    "ein,fym",
    [("100000041", "  "), ("100000042", " 0"), ("100000043", "0 ")],
)
def test_fiscal_year_month_with_a_blank_digit_is_not_treated_as_zero(ein, fym):
    result = run_case("synth_c")
    assert field(output_record(result, ein), entval.F_FYM) == fym


# ------------------------------------------------------------------ 2000-PROC


def test_every_input_record_is_written_even_when_it_errors():
    for case in ("shipped", "synth_a", "synth_b", "synth_c", "empty"):
        result = run_case(case)
        assert result.read_count == result.written_count == len(result.records)


def test_one_record_can_raise_several_error_codes_in_edit_order():
    result = run_case("synth_a")
    lines = [line for line in result.report_text.splitlines() if "990000018" in line]
    assert [line[19:23] for line in lines] == ["E101", "E102"]


def test_empty_input_produces_empty_output_and_an_empty_report():
    result = run_case("empty")
    assert result.output_bytes == b""
    assert result.report_text == ""
    assert result.console == [
        "ENTVAL  READ    000000",
        "ENTVAL  WRITTEN 000000",
        "ENTVAL  ERRORS  000000",
        "ENTVAL  NC CORR 000000",
    ]
