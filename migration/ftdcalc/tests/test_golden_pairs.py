"""Whole-file equivalence against the two COBOL-captured golden pairs.

The expected files under fixtures/ are the output of src/FTDCALC.cbl compiled by
GnuCOBOL 3.1.2 and run on the inputs stored alongside them; nothing in this
suite derives an expected value from IRM 20.1.4.
"""


def test_shipped_fixtures_module_file_is_byte_identical(shipped):
    assert shipped.python_modules == shipped.cobol_modules


def test_shipped_fixtures_report_is_line_identical(shipped):
    assert shipped.python_report == shipped.cobol_report


def test_shipped_fixtures_counters_match_cobol_display(shipped):
    assert shipped.python_counters == shipped.cobol_counters


def test_synthetic_fixtures_module_file_is_byte_identical(synthetic):
    assert synthetic.python_modules == synthetic.cobol_modules


def test_synthetic_fixtures_report_is_line_identical(synthetic):
    assert synthetic.python_report == synthetic.cobol_report


def test_synthetic_fixtures_counters_match_cobol_display(synthetic):
    assert synthetic.python_counters == synthetic.cobol_counters


def test_every_input_module_is_written_unconditionally(shipped):
    assert shipped.cobol_counters["read"] == shipped.cobol_counters["written"]
    assert len(shipped.python_modules) == len(shipped.cobol_modules)
