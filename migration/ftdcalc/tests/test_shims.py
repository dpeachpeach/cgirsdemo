"""Shim-level checks for the two subprograms FTDCALC calls.

FTDCALC calls the COBOL shims src/DATCNV.cbl and src/PENACC.cbl; the HLASM of
the same names under src/asm/ does not execute and was not ported.  The
expectations below are the shim behaviour observed through FTDCALC's own output
(see fixtures/synthetic), reduced to the smallest inputs that show it.
"""

from decimal import Decimal

import ftdcalc


def test_datcnv_rejects_a_julian_day_beyond_the_year_length():
    rc, _, _ = ftdcalc.datcnv("G", jul=2023400)
    assert rc == "8"


def test_datcnv_accepts_day_366_only_in_a_leap_year():
    assert ftdcalc.datcnv("G", jul=2024366)[0] == "0"
    assert ftdcalc.datcnv("G", jul=2023366)[0] == "8"


def test_datcnv_treats_a_century_year_as_common_unless_divisible_by_400():
    assert ftdcalc.datcnv("G", jul=2100366)[0] == "8"
    assert ftdcalc.datcnv("G", jul=2000366)[0] == "0"


def test_datcnv_converts_a_leap_century_date_to_gregorian():
    rc, greg, _ = ftdcalc.datcnv("G", jul=2000100)
    assert (rc, greg) == ("0", 20000409)


def test_datcnv_rejects_an_unknown_function_byte():
    assert ftdcalc.datcnv("X", greg=20230715)[0] == "8"


def test_penacc_rounds_half_up_and_accumulates():
    rc, amount, accum = ftdcalc.penacc(
        Decimal("1000.25"), Decimal("0.0200"), Decimal("0.00"))
    assert (rc, amount, accum) == ("0", Decimal("20.01"), Decimal("20.01"))


def test_penacc_rejects_a_negative_base_without_accumulating():
    rc, amount, accum = ftdcalc.penacc(
        Decimal("-100.00"), Decimal("0.1000"), Decimal("5.00"))
    assert (rc, amount, accum) == ("8", Decimal("0.00"), Decimal("5.00"))


def test_penacc_drops_high_order_digits_when_the_amount_overflows():
    rc, amount, _ = ftdcalc.penacc(
        Decimal("99999999999.99"), Decimal("0.1000"), Decimal("0.00"))
    assert (rc, amount) == ("0", Decimal("0.00"))
