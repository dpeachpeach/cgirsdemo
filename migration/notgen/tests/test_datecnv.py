"""Characterization tests for the DATECNV / DATCNV shims NOTGEN calls.

Expected values were captured by compiling a throwaway COBOL caller in a
scratch tree against the shipped src/DATECNV.cbl and src/DATCNV.cbl modules
(GnuCOBOL 3.1.2) and recording what came back in the parm block.  The HLASM
under src/asm/ does not execute and was not consulted.
"""

import pytest

from notgen import datcnv, datecnv_call, integer_of_date, DvParm

# (func, greg-in, jul-in) -> (greg-out, jul-out, dow-out, rc-out)
CAPTURED = [
    ("B", 20260815, 0, 20260817, 2026229, 1, "0"),
    ("B", 20260703, 0, 20260703, 2026184, 5, "0"),
    ("B", 20261225, 0, 20261228, 2026362, 1, "0"),
    ("B", 20270416, 0, 20270419, 2027109, 1, "0"),
    ("J", 20240229, 0, 20240229, 2024060, 4, "0"),
    ("J", 20260001, 0, 20260001, 0, 7, "0"),
    ("J", 20260015, 0, 20260015, 0, 7, "0"),
    ("J", 20261301, 0, 20261301, 0, 7, "0"),
    ("J", 0, 0, 0, 0, 7, "0"),
    ("J", 20260732, 0, 20260732, 0, 7, "0"),
    ("J", 20260229, 0, 20260229, 2026060, 7, "0"),
    ("J", 16010101, 0, 16010101, 1601001, 1, "0"),
    ("J", 19000301, 0, 19000301, 1900060, 4, "0"),
    ("J", 20000301, 0, 20000301, 2000061, 3, "0"),
    ("J", 19000229, 0, 19000229, 1900060, 7, "0"),
    ("J", 20000229, 0, 20000229, 2000060, 2, "0"),
    ("G", 0, 2024060, 20240229, 2024060, 4, "0"),
    ("G", 0, 2026366, 0, 2026366, 7, "0"),
    ("X", 20260815, 0, 20260815, 0, 0, "8"),
]


@pytest.mark.parametrize("func,greg,jul,xgreg,xjul,xdow,xrc", CAPTURED)
def test_parm_block_matches_cobol(func, greg, jul, xgreg, xjul, xdow, xrc):
    parm = datecnv_call(func, greg=greg, jul=jul)
    assert (parm.greg, parm.jul, parm.dow, parm.rc) == (xgreg, xjul, xdow, xrc)


def test_business_day_shift_walks_saturday_to_the_following_monday():
    parm = datecnv_call("B", greg=20260815)
    assert (parm.greg, parm.jul, parm.dow) == (20260817, 2026229, 1)


def test_holiday_table_shifts_the_holiday_itself_but_has_no_observed_rule():
    # 25 December 2026 is a Friday and matches table entry 1225, so the date
    # walks through the weekend to Monday 28 December.
    assert datecnv_call("B", greg=20261225).greg == 20261228
    # 4 July 2026 falls on a Saturday.  IRC 7503 would observe it on the
    # preceding Friday, 3 July; the table only matches the holiday's own
    # month/day, so 3 July is treated as an ordinary business day.
    assert datecnv_call("B", greg=20260703).greg == 20260703


def test_holiday_table_ignores_the_year_so_movable_dates_move_every_year():
    # 0416 is Emancipation Day observed in 2026 only; 16 April 2027 is still
    # shifted, to Monday 19 April.
    assert datecnv_call("B", greg=20270416).greg == 20270419


def test_datcnv_error_code_is_written_over_the_day_of_week_byte():
    # DATECNV passes DV-PARM(1:24); DATCNV's RC sits where DATECNV keeps DOW.
    parm = DvParm(func="J", greg=20260001)
    datcnv(parm)
    assert parm.dow == 8
    assert parm.jul == 0


def test_datcnv_failure_never_reaches_the_datecnv_return_code():
    # Because of the layout mismatch above, DVP-RC is still "0" when DATECNV
    # tests it, so an invalid date is reported as a successful conversion
    # with a julian date of zero.
    parm = datecnv_call("J", greg=20260001)
    assert parm.rc == "0"
    assert parm.jul == 0


def test_datcnv_accepts_a_day_that_does_not_exist_in_the_month():
    # 29 February 2026 passes DATCNV's KD <= 31 check and converts to day 60,
    # while INTEGER-OF-DATE rejects it and leaves the day of week at 7.
    parm = datecnv_call("J", greg=20260229)
    assert (parm.jul, parm.dow, parm.rc) == (2026060, 7, "0")


def test_century_leap_rule_is_the_full_400_year_rule():
    # 1900 is not a leap year and 2000 is; 1 March converts to day 60 and 61.
    assert datecnv_call("J", greg=19000301).jul == 1900060
    assert datecnv_call("J", greg=20000301).jul == 2000061


def test_integer_of_date_returns_zero_for_dates_the_runtime_rejects():
    assert integer_of_date(16010101) == 1
    assert integer_of_date(20260015) == 0
    assert integer_of_date(0) == 0


def test_unknown_function_byte_returns_rc_8_and_leaves_the_parm_alone():
    parm = datecnv_call("X", greg=20260815)
    assert (parm.rc, parm.jul, parm.dow) == ("8", 0, 0)
