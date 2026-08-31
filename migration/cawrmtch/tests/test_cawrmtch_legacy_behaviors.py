"""Named characterization of individual CAWRMTCH behaviours.

Every expected value here was captured from the GnuCOBOL build of
src/CAWRMTCH.cbl; `only()` re-asserts that the port and the captured COBOL
output agree before the behaviour itself is asserted. Test names record the
behaviour honestly, including where it is a defect.
"""

from conftest import cobol_counters, cobol_report, only, python_run, select


def test_941_only_group_is_flagged_even_when_the_tolerance_would_absorb_it():
    """A group with no W-2 gets condition C004 with no tolerance test at all,
    so a zero-liability group is reported as a discrepancy of 0.00."""
    line = only("s1_941only", "999000005", "2023")
    assert line["code"] == "C004"
    assert line["text"] == "NO W2 DATA FROM SSA"
    assert line["liability"].strip() == "0.00"
    assert line["difference"].strip() == "0.00"


def test_941_only_liability_is_reported_as_a_negative_difference():
    line = only("s1_941only", "999000001", "2023")
    assert line["w2"].strip() == "0.00"
    assert line["liability"].strip() == "5000.00"
    assert line["difference"] == "     5000.00-"


def test_941_groups_after_w2_end_of_file_still_report_c004():
    """Once the W-2 file hits AT END its key becomes HIGH-VALUES, so every
    remaining 941 group falls through the MKEY < WKEY leg."""
    line = only("s1_941only", "999000009", "2023")
    assert line["code"] == "C004"


def test_w2_only_rows_are_counted_separately_and_not_as_discrepancies():
    """C005 increments its own counter (C4) while C004 increments the
    discrepancy counter (C5) — the two orphan conditions are counted
    inconsistently."""
    _, counters = python_run("s1_941only")
    assert counters == cobol_counters("s1_941only")
    assert "CAWRMTCH W2 ONLY 000001" in counters
    assert "CAWRMTCH DISCREP 000003" in counters


def test_tolerance_is_truncated_rather_than_rounded_at_two_decimals():
    """WTOL = WLIA * 0.01 has no ROUNDED, so 1% of 20,000.99 becomes 200.00
    instead of 200.01 and a variance of exactly 200.01 is reported."""
    line = only("s4_tolerance", "999000030", "2023")
    assert line["liability"].strip() == "20000.99"
    assert line["code"] == "C002"
    assert line["difference"] == "      200.01 "


def test_variance_exactly_equal_to_the_tolerance_is_in_balance():
    line = only("s4_tolerance", "999000031", "2023")
    assert line["code"] == "C001"
    assert line["difference"] == "      100.00 "


def test_one_cent_past_the_tolerance_is_a_discrepancy():
    line = only("s4_tolerance", "999000032", "2023")
    assert line["code"] == "C003"
    assert line["text"] == "941 EXCEEDS W2 REPORTED"
    assert line["difference"] == "      100.01-"


def test_hundred_dollar_tolerance_floor_absorbs_a_total_variance_on_small_accounts():
    """The floor is a flat 100.00, so a 50.00 liability with no withholding
    reported at all still passes as IN BALANCE."""
    line = only("s4_tolerance", "999000033", "2023")
    assert line["code"] == "C001"
    assert line["w2"].strip() == "0.00"
    assert line["liability"].strip() == "50.00"


def test_liability_over_nine_digits_loses_its_high_order_digit_in_the_report():
    """CR-941 and CR-DIFF are PIC ZZZZZZZZ9.99 but WLIA is S9(11)V99, so
    1,234,567,890.12 prints as 234,567,890.12."""
    line = only("s5_overflow", "999000040", "2023")
    assert line["liability"] == "234567890.12"
    assert line["difference"] == "234567885.12-"
    assert line["code"] == "C003"


def test_group_sums_every_mft01_module_in_the_tax_year():
    """1000.11 + 2000.22 + 3000.33 over three quarters of 2023."""
    line = only("s2_multimodule", "999000010", "2023")
    assert line["liability"].strip() == "6000.66"
    assert line["difference"].strip() == "0.00"
    assert line["code"] == "C001"


def test_modules_with_other_mfts_are_excluded_from_the_941_liability():
    """The 9999.99 MFT 02 module for the same EIN and year is skipped, and the
    2024 module breaks into its own group."""
    lines, _ = python_run("s2_multimodule")
    assert lines == cobol_report("s2_multimodule")
    assert len(lines) == 2
    assert select(lines, "999000010", "2024")[0]["liability"].strip() == "7777.77"


def test_w2_wages_are_never_compared_only_withholding():
    """80,000.00 of wages against 6,000.66 of liability is IN BALANCE because
    only HW-WHLD reaches the comparison; HW-WAGE is loaded and never used."""
    line = only("s2_multimodule", "999000010", "2023")
    assert line["w2"].strip() == "6000.66"
    assert line["code"] == "C001"


def test_duplicate_w2_row_for_a_matched_group_is_reported_as_no_941_module():
    """The module file has already advanced past the group, so the second W-2
    row for the same EIN and year takes the W2-only leg."""
    lines, counters = python_run("s3_dup_w2")
    assert lines == cobol_report("s3_dup_w2")
    assert counters == cobol_counters("s3_dup_w2")
    rows = select(lines, "999000020", "2023")
    assert [row["code"] for row in rows] == ["C001", "C005"]
    assert rows[1]["text"] == "W2 FILED - NO 941 MODULE"
    assert rows[1]["liability"].strip() == "0.00"


def test_report_carries_no_header_or_trailer_and_one_line_per_condition():
    lines, counters = python_run("shipped")
    assert lines == cobol_report("shipped")
    groups = int(counters[0].split()[-1])
    w2_only = int(counters[3].split()[-1])
    assert len(lines) == groups + w2_only


def test_trailing_blanks_are_stripped_so_positive_differences_are_shorter():
    lines, _ = python_run("shipped")
    assert lines == cobol_report("shipped")
    assert {len(line) for line in lines} == {96, 97}
