"""Characterization tests for the ENTVAL port.

Every expected value in this file was captured by running the GnuCOBOL build of
src/ENTVAL.cbl (with src/NAMCTL.cbl as the called subprogram) — never derived
from IRM 3.13.2 or from the rule as we understand it. Where the legacy program
is wrong, the test asserts the wrong answer and says so in its name.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import entval  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(os.path.dirname(HERE), "fixtures")
RECLEN = entval.RECLEN


def load_input(name):
    return entval.read_records(os.path.join(FIX, name))


def load_dat(name):
    with open(os.path.join(FIX, name), "r", newline="") as fh:
        raw = fh.read()
    return [raw[i:i + RECLEN] for i in range(0, len(raw), RECLEN)]


def load_rpt(name):
    with open(os.path.join(FIX, name), "r", newline="") as fh:
        return fh.read().splitlines()


def run_pair(stem):
    """Run the port over a frozen input; return (records, report lines, counters)."""
    recs, rpt = [], []
    cnt = entval.Counters()
    for rec in load_input(f"{stem}_ENTMAST.txt"):
        cnt.r1 += 1
        res = entval.edit_record(rec)
        recs.append(res.record)
        rpt.extend(res.errors)
        cnt.r3 += res.error_count
        cnt.r4 += res.nc_corrections
        cnt.r2 += 1
    return recs, rpt, cnt


def make_rec(ein, name, nctl, fym="12", ec=" ", ind="1   "):
    rec = (
        ein
        + name.ljust(35)[:35]
        + nctl.ljust(4)[:4]
        + " " * 4
        + "X ST".ljust(35)
        + "CITY".ljust(22)
        + "TX"
        + "000123456"
        + fym
        + ec
        + ind
        + "000000000"
        + " " * 14
    )
    assert len(rec) == RECLEN
    return rec


# --------------------------------------------------------------------------
# Golden pairs: whole-file equivalence against the COBOL's actual output
# --------------------------------------------------------------------------


@pytest.mark.parametrize("stem", ["shipped", "synthetic", "edge", "probe"])
def test_golden_output_file_matches_cobol(stem):
    recs, _, _ = run_pair(stem)
    assert recs == load_dat(f"{stem}_ENTVAL.dat")


@pytest.mark.parametrize("stem", ["shipped", "synthetic", "edge", "probe"])
def test_golden_error_report_matches_cobol(stem):
    _, rpt, _ = run_pair(stem)
    assert rpt == load_rpt(f"{stem}_ENTERR.rpt")


@pytest.mark.parametrize(
    "stem,expected",
    [
        ("shipped", (52, 52, 1, 10)),
        ("synthetic", (13, 13, 4, 2)),
        ("edge", (5, 5, 1, 0)),
        ("probe", (10, 10, 0, 0)),
    ],
)
def test_golden_display_counters_match_cobol(stem, expected):
    _, _, cnt = run_pair(stem)
    assert (cnt.r1, cnt.r2, cnt.r3, cnt.r4) == expected


def test_output_record_length_is_150_and_count_equals_input_count():
    recs, _, cnt = run_pair("shipped")
    assert all(len(r) == RECLEN for r in recs)
    assert len(recs) == cnt.r1 == cnt.r2


# --------------------------------------------------------------------------
# 2200-PFX — EIN prefix against the hard-coded campus table
# --------------------------------------------------------------------------


def test_prefix_table_has_thirty_entries_in_source_order():
    assert entval.PFXENT == [
        "10", "12", "20", "26", "27", "45", "46", "47", "81", "82",
        "83", "84", "85", "86", "87", "88", "91", "92", "93", "94",
        "95", "98", "11", "13", "16", "17", "35", "38", "43", "44",
    ]


def test_unlisted_prefix_writes_e101_and_leaves_record_unchanged():
    rec = make_rec("990001234", "ZZBAD PREFIX CORP", "ZZBA")
    res = entval.edit_record(rec)
    assert res.errors == ["ENTVAL  990001234  E101  PREFIX NOT IN CAMPUS TABLE"]
    assert res.error_count == 1
    assert res.record == rec


def test_listed_prefix_produces_no_e101():
    res = entval.edit_record(make_rec("100002008", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456", "ABCD"))
    assert res.errors == []


def test_e101_echoes_a_non_numeric_ein_verbatim_instead_of_editing_it():
    """EL-EIN is PIC 9(09) but a blank-filled EIN prints as blanks, not zeros."""
    res = entval.edit_record(make_rec("  0003004", "BLANK PREFIX CO", "BLAN"))
    assert res.errors == ["ENTVAL    0003004  E101  PREFIX NOT IN CAMPUS TABLE"]


def test_prefix_check_only_reads_first_two_digits_so_valid_campus_is_position_blind():
    """'10' passes for any EIN starting 10, including EIN ranges no campus issues."""
    assert entval.edit_record(make_rec("109999999", "ZZ CO ZZZZ", "ZZCO")).errors == []


# --------------------------------------------------------------------------
# 2300-NCTL / NAMCTL — name control derivation
# --------------------------------------------------------------------------


def test_matching_name_control_produces_no_error_and_no_correction():
    res = entval.edit_record(make_rec("100002012", "MATCHING NCTL CO", "MATC"))
    assert res.errors == []
    assert res.nc_corrections == 0


def test_mismatched_name_control_is_corrected_in_place_and_counted_separately():
    rec = make_rec("100002007", "THE  DOUBLE SPACE CO", "THED")
    res = entval.edit_record(rec)
    assert res.errors == [
        "ENTVAL  100002007  E103  NAME CONTROL MISMATCH - CORRECTED         THED  DOUB"
    ]
    assert res.nc_corrections == 1
    assert res.error_count == 0  # E103 increments R4, not R3
    assert res.record[entval.NCTL] == "DOUB"


def test_undeliverable_name_control_writes_e102_and_keeps_the_old_value():
    rec = make_rec("100002001", "-.,' ", "XXXX")
    res = entval.edit_record(rec)
    assert res.errors == [
        "ENTVAL  100002001  E102  NAME CONTROL NOT DERIVABLE                XXXX"
    ]
    assert res.record[entval.NCTL] == "XXXX"


def test_name_control_concatenates_across_words_instead_of_using_the_first_word():
    """IRM 3.13.2 derives from the first significant word; NAMCTL squeezes the
    whole name, so 'A B C CORP' yields 'ABCC'."""
    assert entval.namctl("A B C CORP") == ("ABCC", "0")
    assert entval.edit_record(make_rec("100002004", "A B C CORP", "ABCC")).errors == []


def test_leading_the_is_dropped_even_when_it_leaves_nothing_behind():
    assert entval.namctl("THE") == ("    ", "8")


def test_leading_the_is_dropped_for_a_full_width_name():
    assert entval.namctl("THE ABCDEFGHIJKLMNOPQRSTUVWXYZ01234") == ("ABCD", "0")


def test_the_is_only_dropped_at_the_start_of_the_field():
    assert entval.namctl("TRAILING THE CO THE") == ("TRAI", "0")
    assert entval.namctl("THEATER SUPPLY CO") == ("THEA", "0")
    assert entval.namctl("  THE AVOCET") == ("THEA", "0")


def test_punctuation_and_spaces_are_stripped_but_digits_are_kept():
    assert entval.namctl("O'HARE-SMITH, JR. CO") == ("OHAR", "0")
    assert entval.namctl("3M CO") == ("3MCO", "0")


def test_lower_case_name_is_upper_cased_before_derivation():
    assert entval.namctl("lower case name co") == ("LOWE", "0")


def test_short_derived_name_control_is_space_padded_to_four():
    assert entval.namctl("AB") == ("AB  ", "0")


def test_name_control_ignores_the_dead_word_count_from_1000_cntwd():
    """WK04 is computed and never read; word count cannot affect the result."""
    assert entval.namctl("ONEWORD")[0] == entval.namctl("ONE WORD")[0] == "ONEW"


def test_e102_short_circuits_the_mismatch_check():
    """RC 8 does GO TO 2300-X, so no E103 is written for the same record."""
    res = entval.edit_record(make_rec("100002002", "THE", "THE "))
    assert [ln[19:23] for ln in res.errors] == ["E102"]


# --------------------------------------------------------------------------
# 2400-FRC — employment code / 940 filing requirement, and fiscal year month
# --------------------------------------------------------------------------


def test_ec_f_with_940_requirement_writes_e104_and_blanks_the_940_indicator():
    rec = make_rec("100002010", "both EC F and 940", "BOTH", ec="F", ind="11  ")
    res = entval.edit_record(rec)
    assert res.errors == ["ENTVAL  100002010  E104  EC F INCOMPATIBLE WITH 940 FRC"]
    assert res.record[123:127] == "1   "


def test_ec_f_without_940_requirement_is_left_alone():
    rec = make_rec("100002012", "MATCHING NCTL CO", "MATC", ec="F", ind="1   ")
    res = entval.edit_record(rec)
    assert res.errors == []
    assert res.record == rec


def test_940_requirement_without_ec_f_is_left_alone():
    rec = make_rec("100002012", "MATCHING NCTL CO", "MATC", ec="A", ind="11  ")
    res = entval.edit_record(rec)
    assert res.errors == []
    assert res.record == rec


def test_zero_fiscal_year_month_defaults_to_december():
    res = entval.edit_record(make_rec("100002003", "ZERO FYM CO", "ZERO", fym="00"))
    assert res.record[entval.FYM] == "12"
    assert res.errors == []


def test_blank_fiscal_year_month_is_not_treated_as_zero_and_survives_unedited():
    """IF ENT-FYM = ZERO does not fire for blanks, so an unusable FYM is written
    through to ENTVAL.dat with no error line."""
    for fym in ("  ", " 0", "0 "):
        res = entval.edit_record(make_rec("100003001", "BLANK FYM CO", "BLAN", fym=fym))
        assert res.record[entval.FYM] == fym
        assert res.errors == []


def test_out_of_range_fiscal_year_month_is_never_validated():
    res = entval.edit_record(make_rec("100003001", "BAD FYM CO", "BADF", fym="99"))
    assert res.record[entval.FYM] == "99"
    assert res.errors == []


# --------------------------------------------------------------------------
# Report line layout and file-status path
# --------------------------------------------------------------------------


def test_error_line_column_layout_matches_errlin():
    line = entval.errlin("100000001", "E103", "NAME CONTROL MISMATCH - CORRECTED", "AAAA", "BBBB")
    assert line[0:6] == "ENTVAL"
    assert line[8:17] == "100000001"
    assert line[19:23] == "E103"
    assert line[25:65] == "NAME CONTROL MISMATCH - CORRECTED".ljust(40)
    assert line[67:71] == "AAAA"
    assert line[73:77] == "BBBB"
    assert line == line.rstrip()  # LINE SEQUENTIAL trims trailing blanks


def test_missing_input_file_reports_status_35_and_return_code_16(tmp_path):
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(HERE), "entval.py"),
         str(tmp_path / "nope.dat"), str(tmp_path / "o.dat"), str(tmp_path / "o.rpt")],
        capture_output=True, text=True,
    )
    assert out.returncode == 16
    assert out.stdout.strip() == "ENTVAL OPEN FAIL ENTIN 35"


def test_output_and_report_file_statuses_are_never_checked(tmp_path):
    """FS2 and FS3 are declared and never interrogated; a full run reports success
    regardless of what happens on the two output files."""
    src = os.path.join(FIX, "shipped_ENTMAST.txt")
    cnt = entval.run(src, str(tmp_path / "o.dat"), str(tmp_path / "o.rpt"))
    assert (cnt.r1, cnt.r2) == (52, 52)


def test_end_to_end_run_reproduces_the_frozen_golden_files(tmp_path):
    out_dat = tmp_path / "ENTVAL.dat"
    out_rpt = tmp_path / "ENTERR.rpt"
    entval.run(os.path.join(FIX, "shipped_ENTMAST.txt"), str(out_dat), str(out_rpt))
    with open(os.path.join(FIX, "shipped_ENTVAL.dat"), "r", newline="") as fh:
        assert out_dat.read_text() == fh.read()
    with open(os.path.join(FIX, "shipped_ENTERR.rpt"), "r", newline="") as fh:
        assert out_rpt.read_text() == fh.read()
