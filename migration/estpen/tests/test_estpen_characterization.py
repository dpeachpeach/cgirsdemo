"""Characterization tests for the ESTPEN port.

Every expected value in this file was produced by running the compiled
COBOL program `src/ESTPEN.cbl` (GnuCOBOL 3.1.2, fixed format, built by
`tools/build.sh`) and captured under `fixtures/`:

* `fixtures/shipped/`   — the golden pair from the fixtures shipped in
  `data/`: `MODPEN.dat` in, `MODEST.dat` + `ESTPEN.rpt` + the program's
  DISPLAY counters out.
* `fixtures/synthetic/` — the same pair after appending the six
  synthetic module records in
  `fixtures/synthetic/MODMAST-synthetic-rows.txt` to `data/MODMAST.txt`
  in a scratch copy of the repository and re-running `tools/build.sh`
  and `run/pipeline.sh` through step 060.

No expected value here is derived from the IRM, from the comments, or
from the rule as anybody understands it.
"""

from decimal import Decimal

import pytest

from conftest import FIXTURES
from estpen import RECORD_LEN, run, unpack_comp3

SHIPPED = FIXTURES / "shipped"
SYNTHETIC = FIXTURES / "synthetic"


def golden(directory):
    return (
        directory.joinpath("MODPEN.dat").read_bytes(),
        directory.joinpath("MODEST.dat").read_bytes(),
        directory.joinpath("ESTPEN.rpt").read_text().splitlines(),
        directory.joinpath("stdout.txt").read_text(),
    )


def records(blob):
    return [blob[i:i + RECORD_LEN] for i in range(0, len(blob), RECORD_LEN)]


def record_for(blob, ein):
    for record in records(blob):
        if record[0:9].decode() == ein:
            return record
    raise AssertionError(f"no record for EIN {ein}")


def report_for(lines, ein):
    return [line for line in lines if line[8:17] == ein]


def one_record(directory, ein):
    """Run the port over the single input record for `ein` and return its
    output record and report lines, alongside the COBOL's."""
    modin, modest, report, _ = golden(directory)
    result = run(record_for(modin, ein))
    return (
        result.records,
        [line.rstrip() for line in result.report],
        record_for(modest, ein),
        report_for(report, ein),
    )


def pftp(record):
    return unpack_comp3(record[111:117], 2)


# --------------------------------------------------------------------------
# Golden pairs: whole-file equivalence
# --------------------------------------------------------------------------

@pytest.mark.parametrize("directory", [SHIPPED, SYNTHETIC], ids=["shipped", "synthetic"])
def test_module_generation_matches_cobol_byte_for_byte(directory):
    modin, modest, _, _ = golden(directory)
    assert run(modin).records == modest


@pytest.mark.parametrize("directory", [SHIPPED, SYNTHETIC], ids=["shipped", "synthetic"])
def test_report_matches_cobol_line_for_line(directory):
    modin, _, report, _ = golden(directory)
    assert [line.rstrip() for line in run(modin).report] == report


@pytest.mark.parametrize("directory", [SHIPPED, SYNTHETIC], ids=["shipped", "synthetic"])
def test_display_counters_match_cobol(directory):
    modin, _, _, stdout = golden(directory)
    assert run(modin).stdout() == stdout


# --------------------------------------------------------------------------
# Branch-level behaviour, each asserted against the captured COBOL output
# --------------------------------------------------------------------------

def test_non_mft_02_modules_pass_through_untouched():
    modin, modest, report, _ = golden(SHIPPED)
    output = records(run(modin).records)
    for original, produced, expected in zip(records(modin), output, records(modest)):
        if original[9:11] != b"02":
            assert produced == original == expected
    assert not [line for line in report if line[8:17] in
                {r[0:9].decode() for r in records(modin) if r[9:11] != b"02"}]


def test_assessment_below_five_hundred_is_skipped_entirely():
    produced, produced_report, expected, expected_report = one_record(SYNTHETIC, "990000010")
    assert unpack_comp3(expected[78:85], 2) == Decimal("499.99")
    assert expected_report == [] == produced_report
    assert produced == expected == record_for(golden(SYNTHETIC)[0], "990000010")


def test_deposits_equal_to_assessment_leave_no_underpayment():
    for ein in ("850001252", "920001182"):
        produced, produced_report, expected, expected_report = one_record(SHIPPED, ein)
        assert expected_report == [] == produced_report
        assert produced == expected


def test_deposits_exceeding_assessment_leave_no_underpayment():
    produced, produced_report, expected, expected_report = one_record(SHIPPED, "450001217")
    assert expected_report == [] == produced_report
    assert produced == expected
    assert pftp(expected) == Decimal("0.00")


def test_four_quarters_are_reported_with_declining_day_factors():
    produced, produced_report, expected, expected_report = one_record(SHIPPED, "920001140")
    assert produced_report == expected_report
    assert [line[-10:].strip() for line in expected_report] == [
        "770.38", "512.65", "257.73", "84.04"]
    assert [line[58] for line in expected_report] == ["1", "2", "3", "4"]


def test_penalty_accumulates_into_existing_pftp_from_pencalc():
    produced, _, expected, _ = one_record(SHIPPED, "920001140")
    assert pftp(record_for(golden(SHIPPED)[0], "920001140")) == Decimal("21010.41")
    assert pftp(expected) == Decimal("22635.21")
    assert pftp(records(produced)[0]) == pftp(expected)


def test_required_installment_truncates_the_quarter_cent_it_does_not_round():
    """WRQI = WRAP * 0.25 has no ROUNDED clause, so 1000.10 / 4 = 250.025
    lands in the report as 250.02, not 250.03."""
    produced, produced_report, expected, expected_report = one_record(SYNTHETIC, "990000030")
    assert unpack_comp3(expected[78:85], 2) == Decimal("1000.10")
    assert [line[60:71].strip() for line in expected_report] == ["250.02"] * 4
    assert produced_report == expected_report


def test_installment_penalty_rounds_half_up_not_half_even():
    """Quarter 2 on an underpayment of 62.50 computes exactly 0.305; the
    COBOL ROUNDED clause carries it to 0.31."""
    produced, produced_report, expected, expected_report = one_record(SYNTHETIC, "990000040")
    assert [line[60:71].strip() for line in expected_report] == ["62.50"] * 4
    assert expected_report[1][-10:].strip() == "0.31"
    assert produced_report == expected_report


def test_report_underpayment_column_truncates_high_order_digits():
    """WUND is S9(11)V99 but ER-UND is PIC ZZZZZZZ9.99, so an
    underpayment of 24,999,999,999.99 prints as 99999999.99."""
    produced, produced_report, expected, expected_report = one_record(SYNTHETIC, "990000050")
    assert [line[60:71].strip() for line in expected_report] == ["99999999.99"] * 4
    assert produced_report == expected_report


def test_report_amount_column_truncates_high_order_digits():
    """WQAM is S9(9)V99 but ER-AMT is PIC ZZZZZZ9.99: quarter 1 accrues
    183,333,333.33 and prints as 3333333.33."""
    _, produced_report, _, expected_report = one_record(SYNTHETIC, "990000050")
    assert [line[-10:].strip() for line in expected_report] == [
        "3333333.33", "2000000.00", "1333333.33", "0.00"]
    assert produced_report == expected_report


def test_report_amount_column_can_print_zero_for_a_nonzero_accrual():
    """Quarter 4 accrues exactly 20,000,000.00; ER-AMT keeps the low
    seven digits, so the report line reads 0.00 while the module record
    is charged the full amount."""
    produced, _, expected, expected_report = one_record(SYNTHETIC, "990000050")
    assert expected_report[3][-10:].strip() == "0.00"
    charged = pftp(expected) - pftp(record_for(golden(SYNTHETIC)[0], "990000050"))
    assert charged == Decimal("386666666.66")
    assert pftp(records(produced)[0]) == pftp(expected)


def test_sub_cent_underpayment_reports_four_zero_lines_and_counts_as_assessed():
    """An underpayment of 0.01 rounds to 0.00 in every quarter, yet the
    module is still counted in the ASSESSED total and four report lines
    are written."""
    modin, _, _, _ = golden(SYNTHETIC)
    result = run(record_for(modin, "990000060"))
    _, produced_report, expected, expected_report = one_record(SYNTHETIC, "990000060")
    assert len(expected_report) == 4
    assert [line[-10:].strip() for line in expected_report] == ["0.00"] * 4
    assert produced_report == expected_report
    assert result.assessed_count == 1
    assert pftp(records(result.records)[0]) == pftp(expected)


def test_report_line_layout_matches_the_erpt_record():
    _, _, _, expected_report = one_record(SHIPPED, "920001140")
    line = expected_report[0]
    assert line.startswith("ESTPEN  920001140 202206  E601  INSTALLMENT SHORTFALL")
    modin, _, _, _ = golden(SHIPPED)
    assert run(record_for(modin, "920001140")).report[0].rstrip() == line
