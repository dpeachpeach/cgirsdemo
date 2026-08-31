"""Characterization tests for the STATCALC port.

Every expected value in this file is read from a capture of an actual
GnuCOBOL run of src/STATCALC.cbl (see ../fixtures/README.md).  Where the
legacy program is wrong, the test asserts the wrong answer and says so in its
name; the corresponding fix is logged in the port report, not applied here.
"""

import pytest
from conftest import FIXTURES

from statcalc import RECORD_LEN, Statcalc, split_records, unpack_comp3

F_ASED = (66, 4)
F_RSED = (70, 4)
F_CSED = (74, 4)


def load(prefix):
    moddup = split_records((FIXTURES / f"{prefix}_moddup.dat").read_bytes())
    modstat = split_records((FIXTURES / f"{prefix}_modstat.dat").read_bytes())
    report = (FIXTURES / f"{prefix}_statcalc.rpt").read_text().splitlines()
    totals = (FIXTURES / f"{prefix}_totals.txt").read_text().splitlines()
    return moddup, modstat, report, totals


SHIPPED = load("shipped")
SYNTHETIC = load("synthetic")


def execute(golden):
    prog = Statcalc()
    out = prog.run(golden[0])
    return prog, out


def sed_fields(rec):
    return (
        int(unpack_comp3(rec[F_ASED[0] : F_ASED[0] + 4])),
        int(unpack_comp3(rec[F_RSED[0] : F_RSED[0] + 4])),
        int(unpack_comp3(rec[F_CSED[0] : F_CSED[0] + 4])),
    )


def find(golden, ein):
    for i, rec in enumerate(golden[0]):
        if rec[0:9].decode() == ein:
            return i
    raise AssertionError(f"EIN {ein} not in fixture")


def key(rec):
    return rec[0:17].decode()


SHIPPED_RUN = execute(SHIPPED)
SYNTHETIC_RUN = execute(SYNTHETIC)


# --- golden pair, record by record -----------------------------------------

@pytest.mark.parametrize(
    "index", range(len(SHIPPED[0])), ids=[key(r) for r in SHIPPED[0]]
)
def test_shipped_fixture_record_matches_cobol_output(index):
    assert SHIPPED_RUN[1][index] == SHIPPED[1][index]


@pytest.mark.parametrize(
    "index", range(len(SYNTHETIC[0])), ids=[key(r) for r in SYNTHETIC[0]]
)
def test_synthetic_fixture_record_matches_cobol_output(index):
    assert SYNTHETIC_RUN[1][index] == SYNTHETIC[1][index]


def test_shipped_report_matches_cobol_byte_for_byte():
    assert [line.rstrip() for line in SHIPPED_RUN[0].report] == SHIPPED[2]


def test_synthetic_report_matches_cobol_byte_for_byte():
    assert [line.rstrip() for line in SYNTHETIC_RUN[0].report] == SYNTHETIC[2]


@pytest.mark.parametrize(
    "run,golden", [(SHIPPED_RUN, SHIPPED), (SYNTHETIC_RUN, SYNTHETIC)]
)
def test_display_counters_match_cobol(run, golden):
    t = run[0].totals()
    produced = [
        f"STATCALC READ   {t['read']:06d}",
        f"STATCALC WRITTEN{t['written']:06d}",
        f"STATCALC 6YR    {t['6yr']:06d}",
        f"STATCALC SUSPEND{t['suspend']:06d}",
    ]
    assert produced == golden[3]


@pytest.mark.parametrize("golden", [SHIPPED, SYNTHETIC])
def test_every_input_record_is_written_unchanged_apart_from_the_three_sed_fields(golden):
    for src, out in zip(golden[0], golden[1]):
        assert len(out) == RECORD_LEN
        assert src[:66] == out[:66]
        assert src[78:] == out[78:]


# --- due-date and statute arithmetic ---------------------------------------

def test_mft_01_due_date_is_the_28th_of_the_month_after_the_tax_period():
    # 200001014 01 202312 -> RDD 2024-01-28 -> julian 2024028
    i = find(SHIPPED, "200001014")
    assert sed_fields(SHIPPED[1][i])[1:] == (2027028, 2034028)


def test_mft_02_due_date_is_the_15th_four_months_after_the_tax_period():
    # 920001140 02 202206 -> RDD 2022-10-15 -> julian 2022288
    i = find(SHIPPED, "920001140")
    assert sed_fields(SHIPPED[1][i])[0] == 2025288


def test_other_mfts_use_january_31_of_the_following_year():
    i = find(SHIPPED, "100001077")  # MFT 10, tax period 202306
    assert sed_fields(SHIPPED[1][i]) == (2027031, 2027031, 2034031)


def test_ased_and_rsed_are_three_years_and_csed_ten_years_after_the_due_date():
    i = find(SHIPPED, "100001077")
    ased, rsed, csed = sed_fields(SHIPPED[1][i])
    assert ased // 1000 == 2027 and rsed // 1000 == 2027 and csed // 1000 == 2034
    assert ased % 1000 == rsed % 1000 == csed % 1000


def test_year_2000_is_leap_for_the_julian_day_count():
    # 999000003 02 200003 -> RDD 2000-07-15 -> julian 2000197 (196 + leap day)
    i = find(SYNTHETIC, "999000003")
    assert sed_fields(SYNTHETIC[1][i])[0] == 2003197


def test_year_2100_is_not_leap_for_the_julian_day_count():
    # 999000011 02 209911 -> RDD 2100-03-15 -> julian 2100074, not 2100075
    i = find(SYNTHETIC, "999000011")
    assert sed_fields(SYNTHETIC[1][i])[0] == 2103074


# --- statute condition codes ------------------------------------------------

def test_fraud_code_07_sets_ased_to_the_sentinel_9999365():
    i = find(SHIPPED, "200001014")
    assert sed_fields(SHIPPED[1][i])[0] == 9999365
    assert "S302  FRAUD - ASED NOT LIMITED" in SHIPPED[2][1]


def test_form_872_consent_ignores_the_consent_date_in_w8_and_hardcodes_day_105():
    # 910001189 carries statute code 12 with a consent date in W8 positions
    # 4-8; the program moves it to an unused parm field and sets day 105.
    i = find(SHIPPED, "910001189")
    rec = SHIPPED[0][i]
    assert rec[123:131].decode()[3:8] != "     "
    assert sed_fields(SHIPPED[1][i])[0] == 2027105


def test_form_872_consent_does_not_extend_the_ased_beyond_the_normal_three_years():
    # Both the plain and the "extended" ASED land in tax year + 3.
    i = find(SHIPPED, "910001189")  # code 12, tax period 202409
    plain = find(SHIPPED, "100001077")
    assert sed_fields(SHIPPED[1][i])[0] // 1000 == 2024 + 3
    assert sed_fields(SHIPPED[1][plain])[0] // 1000 == 2023 + 3 + 1  # MFT 10 rolls the year


def test_statute_code_bytes_that_are_not_digits_are_treated_as_zero():
    # W8 starts with "AB", "0<" and "0G" respectively: no special handling.
    for ein in ("999000005", "999000007", "999000008"):
        i = find(SYNTHETIC, ein)
        assert sed_fields(SYNTHETIC[1][i])[0] == 2027028


def test_statute_code_with_a_space_beside_the_digit_still_selects_the_fraud_path():
    # W8 " 7......" and "7 ......" both compare equal to 07.
    for ein in ("999000009", "999000010"):
        i = find(SYNTHETIC, ein)
        assert sed_fields(SYNTHETIC[1][i])[0] == 9999365


# --- bankruptcy suspension --------------------------------------------------

def test_bankruptcy_freeze_adds_183_days_to_the_csed():
    # 200001007 carries a V/Z freeze; 2036209 + 183 = 2036392, which then
    # rolls to 2037027 through the day-overflow correction.
    i = find(SHIPPED, "200001007")
    assert sed_fields(SHIPPED[1][i])[2] == 2037027


def test_csed_day_overflow_rolls_the_year_using_365_days_even_in_a_leap_year():
    # 920001140: 2032288 + 183 = 2032471 -> 2033106, i.e. + 1000 - 365.
    i = find(SHIPPED, "920001140")
    assert sed_fields(SHIPPED[1][i])[2] == 2033106


def test_records_without_a_v_or_z_freeze_keep_the_unsuspended_csed():
    i = find(SHIPPED, "100001077")
    assert sed_fields(SHIPPED[1][i])[2] == 2034031


# --- defects reproduced deliberately ----------------------------------------

def test_report_line_for_an_ased_code_carries_the_previous_records_csed():
    # 8000-RPT is performed from 2350-SPCL before 2500-CSED has run, so the
    # CSED column of an S302/S303 line shows the value left over from the
    # last record that reached 2500-CSED.
    lines = SHIPPED[2]
    assert lines[0].startswith("STATCALC  200001007") and lines[0].endswith("2029209 2037027")
    assert lines[1].startswith("STATCALC  200001014")
    assert lines[1].endswith("9999365 2037027")  # 2037027 belongs to the record before


def test_first_report_line_of_a_run_can_only_show_a_csed_from_an_earlier_record():
    # Guard for the same defect: the S302/S303 CSED column is never this
    # record's own CSED unless the two happen to coincide.
    lines = SHIPPED[2]
    codes = [line[31:35] for line in lines]
    assert codes[1] == "S302"
    i = find(SHIPPED, "200001014")
    assert sed_fields(SHIPPED[1][i])[2] != int(lines[1][-7:])


def test_six_year_substantial_omission_counter_is_always_zero():
    # R6 is displayed but never incremented: the six-year statute of
    # IRM 25.6.1 has no implementation in this program.
    assert SHIPPED_RUN[0].totals()["6yr"] == 0
    assert SYNTHETIC_RUN[0].totals()["6yr"] == 0
    assert SHIPPED[3][2].endswith("000000")


def test_deposit_two_year_rsed_branch_is_dead_code():
    # 2400-RSED compares (SY + 2) * 1000 against an RSED already built from
    # SY + 3, so the inner COMPUTE can never run.
    assert "B15" not in SHIPPED_RUN[0].trace
    assert "B15" not in SYNTHETIC_RUN[0].trace


def test_rsed_stays_seven_years_ahead_of_the_csed_even_when_a_deposit_exists():
    # Same defect seen from the data side: no record in either capture has an
    # RSED shifted to the two-year rule.
    for golden in (SHIPPED, SYNTHETIC):
        for src, out in zip(golden[0], golden[1]):
            frz = src[58:66].decode()
            if frz[1] == "V" or frz[6] == "Z":
                continue
            _, rsed, csed = sed_fields(out)
            assert csed - rsed == 7000


def test_an_unconvertible_due_date_silently_reuses_the_previous_records_julian():
    # 999000001 has tax period month 30; MFT 02 adds 4 and subtracts 12 once,
    # leaving month 22.  DATCNV returns RC 8 and leaves DCP-JUL untouched, so
    # this record inherits day 028 from the record before it.
    i = find(SYNTHETIC, "999000001")
    previous = SYNTHETIC[1][i - 1]
    assert sed_fields(SYNTHETIC[1][i])[0] % 1000 == sed_fields(previous)[0] % 1000 == 28
    assert sed_fields(SYNTHETIC[1][i])[0] == 2027028


def test_datcnv_return_code_is_never_inspected_by_statcalc():
    # The record above is written to MODSTAT like any other.
    i = find(SYNTHETIC, "999000001")
    assert SYNTHETIC[1][i][0:17] == SYNTHETIC[0][i][0:17]
    assert len(SYNTHETIC[1]) == len(SYNTHETIC[0])


# --- field encoding ---------------------------------------------------------

def test_sed_fields_are_written_as_unsigned_packed_decimal_with_an_f_sign_nibble():
    for out in SHIPPED[1]:
        for off in (66, 70, 74):
            assert out[off + 3] & 0x0F == 0x0F
