"""Whole-file golden pairs.

Every expected value in this file is a byte-for-byte capture of what
src/DUPCHK.cbl actually wrote:
  fixtures/shipped/    -- the fixtures committed in data/, via tools/build.sh
                          + run/pipeline.sh (BLDFIX then DUPCHK)
  fixtures/synthetic/  -- MODMAST.txt / TRANIN.txt built in a scratch clone to
                          reach branches the shipped fixtures never execute,
                          run through the unmodified COBOL the same way
"""


def test_shipped_module_generation_matches_cobol_byte_for_byte(shipped):
    assert shipped.result.modules == shipped.modules_out


def test_shipped_report_matches_cobol_line_for_line(shipped):
    assert shipped.result.report == shipped.report


def test_shipped_counters_match_cobol_displays(shipped):
    assert shipped.result.counters.display_lines() == shipped.counters


def test_synthetic_module_generation_matches_cobol_byte_for_byte(synthetic):
    assert synthetic.result.modules == synthetic.modules_out


def test_synthetic_report_matches_cobol_line_for_line(synthetic):
    assert synthetic.result.report == synthetic.report


def test_synthetic_counters_match_cobol_displays(synthetic):
    assert synthetic.result.counters.display_lines() == synthetic.counters
