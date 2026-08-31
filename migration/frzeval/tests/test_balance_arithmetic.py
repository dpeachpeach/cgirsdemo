"""Balance computation and PIC ZZZZZZZZ9.99- editing.

The expected strings are the balance columns the legacy program actually wrote
into data/FRZEVAL.rpt for these modules (fixtures/synthetic/FRZEVAL.rpt),
including the two truncations it performs. The report is LINE SEQUENTIAL, so
GnuCOBOL strips the trailing blanks -- a positive amount therefore ends without
the sign position.
"""

from decimal import Decimal

import frzeval
from conftest import run_one

BALANCE_START = 78


def golden_balance(golden, ein):
    (line,) = golden.expected_report_for(ein)
    return line[BALANCE_START:]


def test_balance_column_is_the_penalty_inclusive_module_balance(shipped):
    _, line, _ = run_one(shipped.record_for("200001329"))
    assert line[BALANCE_START:] == golden_balance(shipped, "200001329")


def test_negative_balance_prints_a_trailing_minus_sign(synthetic):
    _, line, _ = run_one(synthetic.record_for("990001002"))
    assert line[BALANCE_START:] == "        0.50-"
    assert line[BALANCE_START:] == golden_balance(synthetic, "990001002")


def test_report_balance_silently_drops_digits_above_999_999_999(synthetic):
    """LEGACY DEFECT, reproduced: WBAL is PIC S9(11)V99 but ZR-BAL is
    PIC ZZZZZZZZ9.99-, so a module balance of 12,345,678,901.23 is reported as
    345,678,901.23. The written module record keeps the real amount."""
    _, line, _ = run_one(synthetic.record_for("990001001"))
    assert line[BALANCE_START:] == "345678901.23"
    assert line[BALANCE_START:] == golden_balance(synthetic, "990001001")


def test_wbal_wraps_at_eleven_integer_digits_before_it_is_reported(synthetic):
    """LEGACY DEFECT, reproduced: the COMPUTE into WBAL has no ON SIZE ERROR,
    so 100,999,999,999.98 wraps to 999,999,999.98 rather than being flagged."""
    _, line, _ = run_one(synthetic.record_for("990001005"))
    assert line[BALANCE_START:] == "999999999.98"
    assert line[BALANCE_START:] == golden_balance(synthetic, "990001005")


def test_zero_balance_prints_a_single_suppressed_zero(shipped):
    _, line, _ = run_one(shipped.record_for("120001322"))
    assert line[BALANCE_START:] == "        0.00"
    assert line[BALANCE_START:] == golden_balance(shipped, "120001322")


def test_edited_balance_field_is_thirteen_characters_wide():
    assert len(frzeval.edit_zr_bal(Decimal("0"))) == 13
    assert len(frzeval.edit_zr_bal(Decimal("-12345.67"))) == 13


def test_packed_decimal_round_trips_through_the_copybook_widths():
    for text in ["0.00", "-1.23", "12345678901.23", "-99999999999.99"]:
        value = Decimal(text)
        raw = frzeval.pack_decimal(value, 13, 2)
        assert len(raw) == 7
        assert frzeval.unpack_decimal(raw, 2) == value
