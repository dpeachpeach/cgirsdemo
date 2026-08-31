"""Golden-pair characterization: the Python output must equal, byte for byte,
what src/PENCALC.cbl produced for the same MODFTD/TRANIN images."""


def test_shipped_module_output_matches_cobol_byte_for_byte(shipped):
    assert shipped.result.mod_out == shipped.cobol_mod_out


def test_shipped_report_matches_cobol(shipped):
    assert shipped.result.report == shipped.cobol_report


def test_shipped_counters_match_cobol_display(shipped):
    c = shipped.result.counters
    assert (c.read, c.written, c.ftf, c.minimum) == (52, 52, 25, 3)


def test_synthetic_module_output_matches_cobol_byte_for_byte(synthetic):
    assert synthetic.result.mod_out == synthetic.cobol_mod_out


def test_synthetic_report_matches_cobol(synthetic):
    assert synthetic.result.report == synthetic.cobol_report


def test_synthetic_counters_match_cobol_display(synthetic):
    c = synthetic.result.counters
    assert (c.read, c.written, c.ftf, c.minimum) == (65, 65, 30, 6)


def test_every_shipped_module_is_written_back_unfiltered(shipped):
    assert shipped.result.counters.read == shipped.result.counters.written
