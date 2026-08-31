"""DATCNV shim and COMP-3 characterization.

The runnable pipeline calls the COBOL shim src/DATCNV.cbl (the HLASM under
src/asm/ does not execute), so the port is against the shim. Expected values
in fixtures/datcnv-golden.txt come from a scratch-tree harness that CALLs the
compiled DATCNV directly.
"""

from decimal import Decimal
from pathlib import Path

import pencalc

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "datcnv-golden.txt"


def _golden_cases():
    cases = []
    for line in GOLDEN.read_text().splitlines():
        if "->" not in line:
            continue
        head, tail = line.split("->")
        func, greg = head.split()
        fields = dict(part.split("=") for part in tail.split())
        cases.append((func, int(greg), fields["GREG"], fields["JUL"], fields["RC"]))
    return cases


def test_datcnv_matches_cobol_harness_goldens():
    assert _golden_cases()
    for func, greg, exp_greg, exp_jul, exp_rc in _golden_cases():
        got_greg, got_jul, got_rc = pencalc.datcnv(func, greg=greg, jul=0)
        assert (f"{got_greg:08d}", f"{got_jul:07d}", got_rc) == (
            exp_greg,
            exp_jul,
            exp_rc,
        ), func + str(greg)


def test_unknown_function_code_returns_rc_8_and_leaves_dates_alone():
    assert pencalc.datcnv("X", greg=20240410, jul=0) == (20240410, 0, "8")


def test_gregorian_conversion_handles_the_three_leap_branches():
    # Day 100 of 1900 (not a leap year), 2000 (leap) and 2024 (leap).
    assert pencalc.datcnv("G", jul=1900100)[0] == 19000410
    assert pencalc.datcnv("G", jul=2000100)[0] == 20000409
    assert pencalc.datcnv("G", jul=2024100)[0] == 20240409


def test_day_366_of_a_non_leap_year_is_rejected():
    assert pencalc.datcnv("G", greg=0, jul=2023366) == (0, 2023366, "8")


def test_comp3_round_trip_preserves_sign_and_scale():
    packed = pencalc.pack_comp3(Decimal("-2015.00"), 11, 2)
    assert packed[-1] & 0x0F == 0x0D
    assert pencalc.unpack_comp3(packed, 2) == Decimal("-2015.00")
    positive = pencalc.pack_comp3(Decimal("2015.00"), 11, 2)
    assert positive[-1] & 0x0F == 0x0C


def test_comp3_store_truncates_high_order_digits_like_cobol():
    assert pencalc.store(Decimal("24999999999.99"), 11, 2) == Decimal(
        "999999999.99"
    )


def test_truncation_never_rounds_up():
    assert pencalc.truncate(Decimal("500.2165"), 2) == Decimal("500.21")
    assert pencalc.truncate(Decimal("-500.2165"), 2) == Decimal("-500.21")
