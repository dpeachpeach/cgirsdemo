"""Per-branch characterization of src/ESTPEN.cbl.

Every expected value below was captured from GnuCOBOL 3.1.2 running the real
program; nothing here is derived from IRM 20.1.3 or from the installment rule
as anyone understands it. Where the COBOL is wrong the test says so in its name.
"""

from decimal import Decimal

import estpen


def run_one(record: bytes):
    out, text, counters = estpen.process(record)
    return out, text.splitlines(), counters


def pftp(record: bytes) -> Decimal:
    return estpen.Module(record).pftp


# ERPT displacements, zero-relative
COL_Q = 58
COL_UND = slice(60, 71)
COL_AMT = slice(72, 82)


def amounts(lines):
    return [ln[COL_AMT].strip() for ln in lines]


def check(case, pair, ein):
    """Assert the port reproduces the COBOL for one record, and return its pieces."""
    modin, modest, lines = case(pair, ein)
    out, got_lines, _ = run_one(modin)
    assert out == modest
    assert got_lines == lines
    return modin, out, got_lines


# --- B3/B4: IF BMF-MFT = 02 -----------------------------------------------

def test_mft_02_module_enters_the_estimated_tax_routine(case):
    _, out, lines = check(case, "shipped", "920001140")
    assert len(lines) == 4
    assert pftp(out) == Decimal("22635.21")


def test_non_mft_02_module_is_copied_forward_untouched(case, goldens):
    modin, modest, lines = case("synthpipe", "990001109")
    assert estpen.Module(modin).mft == 1
    assert estpen.Module(modin).assd == Decimal("900000.00")
    assert lines == []
    out, _, _ = run_one(modin)
    assert out == modin == modest


# --- B5/B6: IF WRAP < 500 -------------------------------------------------

def test_assessment_just_below_the_500_dollar_floor_is_skipped(case):
    _, out, lines = check(case, "synthpipe", "990001010")
    assert estpen.Module(out).assd == Decimal("499.99")
    assert lines == []
    assert pftp(out) == Decimal("0.00")


def test_zero_assessment_is_skipped(case):
    _, _, lines = check(case, "synthpipe", "990001028")
    assert lines == []


def test_assessment_of_exactly_500_dollars_is_not_below_the_floor(case):
    _, out, lines = check(case, "synthpipe", "990001036")
    assert len(lines) == 4
    assert pftp(out) == Decimal("1.94")


def test_negative_assessment_is_skipped_because_500_is_an_unsigned_comparison(case):
    """A credit balance takes the WRAP < 500 exit, so no penalty and no report
    line ever documents that the module was even considered."""
    _, out, lines = check(case, "direct", "991000019")
    assert estpen.Module(out).assd == Decimal("-1000.00")
    assert lines == []


def test_below_floor_module_leaves_an_existing_ftp_penalty_alone(case):
    _, out, lines = check(case, "direct", "991000051")
    assert lines == []
    assert pftp(out) == Decimal("-100.00")


# --- B7/B8: IF WUND NOT > ZERO -------------------------------------------

def test_deposits_exceeding_the_required_installment_produce_no_penalty(case):
    modin, out, lines = check(case, "shipped", "450001217")
    assert estpen.Module(modin).dep > estpen.Module(modin).assd
    assert lines == []
    assert pftp(out) == Decimal("0.00")


def test_deposits_exactly_equal_to_the_assessment_produce_no_penalty(case):
    modin, _, lines = check(case, "shipped", "850001252")
    assert estpen.Module(modin).dep == estpen.Module(modin).assd
    assert lines == []


def test_one_cent_shortfall_still_walks_all_four_installments(case):
    """WUND is 0.01 and every installment rounds to nothing, yet the COBOL still
    writes four report lines saying a shortfall was assessed."""
    _, out, lines = check(case, "synthpipe", "990001087")
    assert len(lines) == 4
    assert amounts(lines) == ["0.00"] * 4
    assert pftp(out) == Decimal("0.00")


def test_one_cent_overpayment_is_erased_by_wpdi_truncation(case):
    """BMF-DEP exceeds BMF-ASSD by a cent, but BMF-DEP * 0.25 truncates into
    WPDI's two decimals, so WUND lands on exactly zero instead of negative and
    the module escapes only via the NOT > ZERO test."""
    modin, _, lines = check(case, "synthpipe", "990001095")
    module = estpen.Module(modin)
    assert module.dep - module.assd == Decimal("0.01")
    assert lines == []


# --- B9-B14: PERFORM VARYING QI / EVALUATE QI ----------------------------

def test_four_installments_use_275_183_92_and_30_day_factors(case):
    """The day counts are hardcoded, so the ratios between the four amounts are
    fixed regardless of the tax period the module is for."""
    _, _, lines = check(case, "direct", "991000027")
    assert amounts(lines) == ["275.00", "183.00", "92.00", "30.00"]
    assert [int(ln[COL_Q]) for ln in lines] == [1, 2, 3, 4]


def test_loop_writes_exactly_four_report_lines_per_assessed_module(case):
    _, _, lines = check(case, "synthpipe", "990001044")
    assert len(lines) == 4


def test_negative_deposit_balance_inflates_the_shortfall(case):
    """WPDI goes negative, so subtracting it adds to WUND: a debit in BMF-DEP
    raises the penalty rather than being ignored."""
    modin, out, lines = check(case, "direct", "991000027")
    assert estpen.Module(modin).dep == Decimal("-50000.00")
    assert lines[0][COL_UND].strip() == "37500.00"
    assert pftp(out) == Decimal("580.00")


# --- arithmetic semantics ------------------------------------------------

def test_wrqi_truncates_rather_than_rounds_the_quarter_of_the_assessment(case):
    """2000.10 * 0.25 is 500.025; WRQI has no ROUNDED, so it stores 500.02."""
    _, _, lines = check(case, "synthpipe", "990001052")
    assert lines[0][COL_UND].strip() == "500.02"


def test_installment_amount_rounds_half_up_not_half_even(case):
    """Quarter 4 computes exactly 3.525. ROUNDED is half-up away from zero, so
    3.53 — banker's rounding would give 3.52 and the suite would fail."""
    _, out, lines = check(case, "synthpipe", "990001044")
    assert amounts(lines) == ["32.31", "21.50", "10.81", "3.53"]
    assert pftp(out) == Decimal("68.15")


def test_repeating_division_by_thirty_rounds_up_on_a_six_tail(case):
    _, out, lines = check(case, "direct", "991000060")
    assert amounts(lines) == ["91.67", "61.00", "30.67", "10.00"]
    assert pftp(out) == Decimal("193.34")


def test_repeating_division_by_thirty_rounds_down_on_a_three_tail(case):
    _, out, lines = check(case, "direct", "991000078")
    assert amounts(lines) == ["73.33", "48.80", "24.53", "8.00"]
    assert pftp(out) == Decimal("154.66")


def test_installments_that_round_to_zero_are_still_reported_as_shortfalls(case):
    _, out, lines = check(case, "synthpipe", "990001060")
    assert amounts(lines) == ["0.01", "0.00", "0.00", "0.00"]
    assert pftp(out) == Decimal("0.01")


# --- undersized fields --------------------------------------------------

def test_report_underpayment_field_silently_drops_high_order_digits(case):
    """WUND is 24999999999.99 but ER-UND is PIC ZZZZZZZ8.99, so the report
    claims a shortfall of 99999999.99 - three digits of the real figure are
    gone and nothing flags it."""
    modin, _, lines = check(case, "synthpipe", "990001079")
    assert estpen.Module(modin).assd == Decimal("99999999999.99")
    assert {ln[COL_UND] for ln in lines} == {"99999999.99"}


def test_report_amount_field_silently_drops_high_order_digits(case):
    """The real quarter-1 amount is 183333333.33 and quarter 4 is 20000000.00;
    ER-AMT is PIC ZZZZZZ9.99, so they print as 3333333.33 and 0.00."""
    _, out, lines = check(case, "synthpipe", "990001079")
    assert amounts(lines) == ["3333333.33", "2000000.00", "1333333.33", "0.00"]
    assert pftp(out) == Decimal("386666666.66")


def test_ftp_penalty_field_wraps_instead_of_raising_a_size_error(case):
    """ADD WACC TO BMF-PFTP has no ON SIZE ERROR. 700000000.00 + 386666666.66
    is 1086666666.66, which does not fit S9(9)V99, so the account is left
    holding 86666666.66 - a billion dollars of penalty quietly discarded."""
    modin, out, _ = check(case, "direct", "991000035")
    assert estpen.Module(modin).pftp == Decimal("700000000.00")
    assert pftp(out) == Decimal("86666666.66")


def test_negative_ftp_penalty_balance_accumulates_arithmetically(case):
    _, out, _ = check(case, "direct", "991000043")
    assert pftp(out) == Decimal("-98.06")


# --- B1/B2: READ AT END / NOT AT END ------------------------------------

def test_empty_input_file_writes_nothing_and_reports_zero_counters():
    out, text, counters = estpen.process(b"")
    assert out == b""
    assert text == ""
    assert (counters.read, counters.written, counters.assessed) == (0, 0, 0)


def test_every_record_read_is_also_written(goldens):
    for modin, _, _, (read, written, _) in goldens.values():
        _, _, counters = estpen.process(modin)
        assert counters.read == counters.written == read == written


# --- report layout ------------------------------------------------------

def test_report_line_carries_the_hardcoded_e601_code_and_text(case):
    _, _, lines = check(case, "shipped", "920001140")
    for line in lines:
        assert line[:6] == "ESTPEN"
        assert line[26:30] == "E601"
        assert line[32:56].rstrip() == "INSTALLMENT SHORTFALL"
        assert line[18:24] == "202206"


def test_counter_display_lines_match_the_cobol_format(goldens):
    _, _, counters = estpen.process(goldens["shipped"][0])
    assert counters.display() == (
        "ESTPEN  READ    000052\n"
        "ESTPEN  WRITTEN 000052\n"
        "ESTPEN  ASSESSED000001\n"
    )
