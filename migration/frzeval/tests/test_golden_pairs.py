"""Whole-file characterization: the Python port must reproduce the COBOL's
MODFRZ.dat, FRZEVAL.rpt and console counters byte for byte.

Fixtures under fixtures/shipped/ are the pipeline's own data/ files; fixtures
under fixtures/synthetic/ come from a scratch tree with five extra MODMAST.txt
records (fixtures/synthetic/MODMAST.txt) put through BLDFIX and steps 000-070.
Every expected value here was captured from bin/FRZEVAL, never derived from
IRM 21.5.6.
"""

import frzeval


def _run(golden):
    return frzeval.run(golden.records)


def test_shipped_fixtures_module_file_matches_cobol(shipped):
    out_records, _, _ = _run(shipped)
    assert out_records == shipped.expected_records


def test_shipped_fixtures_report_matches_cobol(shipped):
    _, report, _ = _run(shipped)
    assert report == shipped.expected_report


def test_shipped_fixtures_console_counters_match_cobol(shipped):
    _, _, counters = _run(shipped)
    assert [
        f"FRZEVAL READ    {counters.read:06d}",
        f"FRZEVAL WRITTEN {counters.written:06d}",
        f"FRZEVAL RFND SUP{counters.refund_suppressed:06d}",
        f"FRZEVAL OFST SUP{counters.offset_suppressed:06d}",
    ] == shipped.expected_console


def test_synthetic_fixtures_module_file_matches_cobol(synthetic):
    out_records, _, _ = _run(synthetic)
    assert out_records == synthetic.expected_records


def test_synthetic_fixtures_report_matches_cobol(synthetic):
    _, report, _ = _run(synthetic)
    assert report == synthetic.expected_report


def test_synthetic_fixtures_console_counters_match_cobol(synthetic):
    _, _, counters = _run(synthetic)
    assert [
        f"FRZEVAL READ    {counters.read:06d}",
        f"FRZEVAL WRITTEN {counters.written:06d}",
        f"FRZEVAL RFND SUP{counters.refund_suppressed:06d}",
        f"FRZEVAL OFST SUP{counters.offset_suppressed:06d}",
    ] == synthetic.expected_console


def test_every_input_record_is_written_unfiltered(shipped):
    out_records, _, counters = _run(shipped)
    assert counters.read == counters.written == len(shipped.records)
    assert all(len(record) == 150 for record in out_records)


def test_empty_input_produces_no_records_and_no_report():
    out_records, report, counters = frzeval.run([])
    assert (out_records, report) == ([], [])
    assert (counters.read, counters.written) == (0, 0)


def test_only_the_r_and_o_freeze_positions_are_modified(synthetic):
    out_records, _, _ = _run(synthetic)
    for source, result in zip(synthetic.records, out_records):
        before = bytearray(source)
        after = bytearray(result)
        before[frzeval.OFF_FRZ_R] = after[frzeval.OFF_FRZ_R] = 0
        before[frzeval.OFF_FRZ_O] = after[frzeval.OFF_FRZ_O] = 0
        assert bytes(before) == bytes(after)
