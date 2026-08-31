"""Characterization tests for the ENTVAL port.

Every expected value in this file comes from a captured run of the COBOL
program `bin/ENTVAL` (GnuCOBOL 3.1.2, fixed format, built by tools/build.sh)
and lives in ../fixtures/. Nothing here is derived from IRM 3.13.2 or from the
rule as anybody understands it. See fixtures/PROVENANCE.md.
"""

import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(os.path.dirname(HERE), "fixtures")
sys.path.insert(0, os.path.dirname(HERE))

import entval  # noqa: E402


def _records(path):
    with open(os.path.join(FIXTURES, path)) as fh:
        return [line.rstrip("\n") for line in fh if line.strip("\n")]


def _load(path):
    with open(os.path.join(FIXTURES, path)) as fh:
        return json.load(fh)


SHIPPED_IN = _records("golden_shipped_input.txt")
SHIPPED_OUT = _records("golden_shipped_output.txt")
SHIPPED_ERR = _records("golden_shipped_enterr.rpt")
SHIPPED_COUNTERS = _load("golden_shipped_counters.json")
SYNTHETIC = _load("synthetic_cases.json")
OPEN_FAILURE = _load("golden_open_failure.json")
BY_NAME = {case["name"]: case for case in SYNTHETIC}


def _run_case(name):
    case = BY_NAME[name]
    return case, entval.run([case["input"]])


# --- golden pair: the shipped data/ENTMAST.txt fixtures ------------------


def test_shipped_fixtures_produce_identical_output_records():
    result = entval.run(SHIPPED_IN)
    assert result.outputs == SHIPPED_OUT


def test_shipped_fixtures_produce_identical_error_report():
    result = entval.run(SHIPPED_IN)
    assert [line.rstrip() for line in result.errors] == SHIPPED_ERR


def test_shipped_fixtures_produce_identical_counters():
    result = entval.run(SHIPPED_IN)
    assert result.counters == SHIPPED_COUNTERS


def test_shipped_fixture_counter_display_lines():
    result = entval.run(SHIPPED_IN)
    assert entval.counter_lines(result.counters) == [
        "ENTVAL  READ    000052",
        "ENTVAL  WRITTEN 000052",
        "ENTVAL  ERRORS  000001",
        "ENTVAL  NC CORR 000010",
    ]


# --- every synthetic case, output record, report lines and counters ------


@pytest.mark.parametrize("case", SYNTHETIC, ids=[c["name"] for c in SYNTHETIC])
def test_synthetic_case_matches_cobol_capture(case):
    result = entval.run([case["input"]])
    assert result.outputs == [case["output"]]
    assert [line.rstrip() for line in result.errors] == case["errors"]
    assert result.counters == case["counters"]


# --- named behaviors, including the defects -----------------------------


def test_the_is_dropped_even_when_only_one_word_follows():
    """Legacy defect: NAMCTL drops a leading 'THE ' unconditionally.

    IRM 3.13.2 keeps 'THE' when a single word follows, and NAMCTL even counts
    the words into WK04 -- then never looks at the count. So 'THE AVOCET'
    derives AVOC, the record's THEA is overwritten, and an E103 is reported.
    Ten of the 52 shipped entity records are corrected this way.
    """
    case, result = _run_case("the_plus_single_word_drops_the")
    assert result.outputs[0][44:48] == "AVOC"
    assert result.errors[0].rstrip() == case["errors"][0]
    assert "E103" in result.errors[0]


def test_leading_space_defeats_the_drop():
    """A single leading blank makes WK01(1:4) ' THE', so DROPTHE misses and
    the derived name control keeps THE: THEA, not AVOC."""
    case, result = _run_case("leading_space_defeats_the_drop")
    assert result.outputs[0][44:48] == "THEA"
    assert result.errors == []
    assert result.counters == case["counters"]


def test_name_control_corrections_are_not_counted_as_errors():
    """E103 bumps R4 only; the ERRORS counter (R3) stays at zero even though a
    line was written to the error report."""
    case, result = _run_case("the_plus_single_word_drops_the")
    assert result.counters["errors"] == 0
    assert result.counters["nc_corr"] == 1
    assert len(result.errors) == 1
    assert case["counters"] == result.counters


def test_underivable_name_skips_the_mismatch_edit_and_keeps_stale_nctl():
    """2300-NCTL's GO TO 2300-X means an E102 record never reaches the
    mismatch edit, so its existing name control is left as it was."""
    case, result = _run_case("name_all_punctuation_not_derivable")
    assert result.outputs[0][44:48] == "ABCD"
    assert [line.rstrip() for line in result.errors] == case["errors"]
    assert all("E103" not in line for line in result.errors)


def test_name_of_only_the_is_not_derivable():
    """'THE' alone: DROPTHE leaves WK01 blank, SQUEEZE yields spaces, NAMCTL
    returns RC 8 and ENTVAL reports E102."""
    case, result = _run_case("name_only_the_not_derivable")
    assert "E102" in result.errors[0]
    assert [line.rstrip() for line in result.errors] == case["errors"]


def test_prefix_not_in_campus_table_reports_e101_and_still_writes_record():
    case, result = _run_case("prefix_not_in_campus_table")
    assert "E101" in result.errors[0]
    assert result.counters == {"read": 1, "written": 1, "errors": 1,
                               "nc_corr": 0}
    assert result.outputs[0] == case["output"]


def test_prefix_zero_zero_is_rejected():
    case, result = _run_case("prefix_zero_zero")
    assert [line.rstrip() for line in result.errors] == case["errors"]


def test_ec_f_with_940_frc_blanks_the_indicator():
    case, result = _run_case("ec_f_with_940_blanked")
    assert result.outputs[0][124] == " "
    assert "E104" in result.errors[0]
    assert result.outputs[0] == case["output"]


def test_ec_f_without_940_frc_is_left_alone():
    case, result = _run_case("ec_f_without_940_no_error")
    assert result.errors == []
    assert result.outputs[0] == case["input"]


def test_fym_zero_defaults_to_december_without_an_error_line():
    case, result = _run_case("fym_zero_defaults_to_twelve")
    assert result.outputs[0][120:122] == "12"
    assert result.errors == []
    assert result.counters == case["counters"]


def test_error_lines_are_written_in_edit_order_e101_e102_e104():
    """One record can raise three edits; the report order is the order the
    paragraphs run in, not the code order of the messages."""
    case, result = _run_case("all_edits_fire_together")
    assert [line[19:23] for line in result.errors] == ["E101", "E102", "E104"]
    assert [line.rstrip() for line in result.errors] == case["errors"]
    assert result.outputs[0][120:122] == "12"


def test_e103_and_e104_both_fire_on_one_record():
    case, result = _run_case("nc_mismatch_and_ec_f_940")
    assert [line[19:23] for line in result.errors] == ["E103", "E104"]
    assert result.counters == case["counters"]


def test_punctuation_and_spaces_are_squeezed_out_of_the_name():
    case, result = _run_case("punctuation_squeezed_out")
    assert result.outputs[0][44:48] == "OHAR"
    assert result.errors == []


def test_single_letter_words_concatenate_into_the_name_control():
    case, result = _run_case("spaces_squeezed_across_words")
    assert result.outputs[0][44:48] == "ABCK"
    assert result.errors == []


def test_short_name_yields_a_space_padded_name_control():
    case, result = _run_case("name_shorter_than_four_chars")
    assert result.outputs[0][44:48] == "AB  "
    assert result.errors == []


def test_three_character_name_mismatches_a_four_character_nctl():
    case, result = _run_case("name_three_chars_mismatch")
    assert result.outputs[0][44:48] == "ABC "
    assert [line.rstrip() for line in result.errors] == case["errors"]


def test_lowercase_name_is_folded_before_derivation():
    case, result = _run_case("lowercase_name_folded")
    assert result.outputs[0][44:48] == "SISK"
    assert result.errors == []


def test_digits_are_ordinary_name_control_characters():
    case, result = _run_case("digits_kept_in_name_control")
    assert result.outputs[0][44:48] == "3MKU"
    assert result.errors == []


def test_thirty_five_character_the_name_survives_the_31_char_move():
    case, result = _run_case("name_exactly_35_chars_starting_the")
    assert result.outputs[0] == case["output"]
    assert result.errors == []


def test_clean_record_passes_through_untouched():
    case, result = _run_case("nctl_already_correct")
    assert result.outputs[0] == case["input"]
    assert result.errors == []
    assert result.counters == {"read": 1, "written": 1, "errors": 0,
                               "nc_corr": 0}


def test_missing_input_file_displays_status_35_and_returns_16(capsys, tmp_path):
    rc = entval.main(["entval.py", str(tmp_path / "nope.dat"),
                      str(tmp_path / "out.dat"), str(tmp_path / "err.rpt")])
    captured = capsys.readouterr()
    assert rc == OPEN_FAILURE["returncode"]
    assert captured.out == OPEN_FAILURE["stdout"]


def test_error_report_line_is_120_bytes_before_line_sequential_trimming():
    """ERRLIN is PIC X(120); the LINE SEQUENTIAL write is what trims it."""
    result = entval.run([BY_NAME["prefix_not_in_campus_table"]["input"]])
    assert len(result.errors[0]) == 120
    assert result.errors[0].rstrip() != result.errors[0]


def test_output_records_are_exactly_150_bytes():
    result = entval.run(SHIPPED_IN)
    assert {len(record) for record in result.outputs} == {150}
