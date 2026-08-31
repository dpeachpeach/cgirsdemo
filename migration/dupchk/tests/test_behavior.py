"""Per-branch characterization of DUPCHK.

Every literal expected value below was read out of a golden capture of an
actual run of src/DUPCHK.cbl (fixtures/shipped/, fixtures/synthetic/), and each
test asserts it against the COBOL capture as well as the Python port, so a test
cannot drift into asserting only what the port happens to do.
"""

import dupchk

FRZ = slice(58, 66)
ASED = slice(66, 70)
TCCNT = slice(131, 134)


def both(golden, key):
    return golden.cobol_module(key), golden.python_module(key)


def both_report(golden, key):
    return golden.cobol_report_for(key), golden.python_report_for(key)


def ased(record):
    return int(dupchk.unpack_decimal(record[ASED], 7))


# --- duplicate filing detection -------------------------------------------


def test_tc150_with_tc976_sets_a_freeze_and_reports_the_976_date(shipped):
    key = "12000132201202303"
    expected_report = [
        "DUPCHK  120001322 01 202303  D201  "
        "DUP FILING - A FREEZE SET               001 000 2024146"
    ]
    for record in both(shipped, key):
        assert record[FRZ].decode() == "A       "
    for report in both_report(shipped, key):
        assert report == expected_report


def test_tc150_with_tc977_reports_zero_976_count_and_zero_976_date(synthetic):
    """C77 alone still sets the freeze, but DR-C prints D76, which is unset."""
    key = "30000000301202312"
    expected_report = [
        "DUPCHK  300000003 01 202312  D201  "
        "DUP FILING - A FREEZE SET               000 001 0000000"
    ]
    for record in both(synthetic, key):
        assert record[FRZ].decode() == "A       "
    for report in both_report(synthetic, key):
        assert report == expected_report


def test_two_tc150_alone_sets_a_freeze_with_zero_976_and_977_counts(synthetic):
    key = "30000000401202312"
    expected_report = [
        "DUPCHK  300000004 01 202312  D201  "
        "DUP FILING - A FREEZE SET               000 000 0000000"
    ]
    for record in both(synthetic, key):
        assert record[FRZ].decode() == "A       "
    for report in both_report(synthetic, key):
        assert report == expected_report


def test_single_tc150_alone_sets_no_freeze(synthetic):
    key = "30000000101202312"
    for record in both(synthetic, key):
        assert record[FRZ].decode() == "        "
    for report in both_report(synthetic, key):
        assert report == []


# --- the TC 560 suppression defect ----------------------------------------


def test_tc560_suppresses_freeze_even_though_tc977_duplicate_is_present(shipped):
    """Legacy defect, reproduced: 2400-EVAL's suppression tests only C76, so a
    TC 977 (ELF) duplicate filing is silently dropped when a TC 560 exists."""
    key = "20000100701202606"
    for record in both(shipped, key):
        assert record[FRZ].decode() == " VL S Z "  # unchanged, no A freeze
    for report in both_report(shipped, key):
        assert [line[29:33] for line in report] == ["D202"]  # no D201 line


def test_tc560_suppresses_freeze_even_for_two_tc150_duplicate_returns(synthetic):
    """Legacy defect, reproduced: the C50 > 1 duplicate is unconditional
    evidence of a duplicate filing, yet the later C76/C60 test clears DUPSW."""
    key = "30000000701202312"
    for record in both(synthetic, key):
        assert record[FRZ].decode() == "        "
    for report in both_report(synthetic, key):
        assert [line[29:33] for line in report] == ["D202"]


# --- TC 560 ASED correction ----------------------------------------------


def test_later_tc560_date_replaces_ased_and_reports_d202(shipped):
    key = "81000113301202306"
    expected_report = [
        "DUPCHK  810001133 01 202306  D202  "
        "TC 560 ASED CORRECTION APPLIED          000 000 2028289"
    ]
    for record in both(shipped, key):
        assert ased(record) == 2028289
    for report in both_report(shipped, key):
        assert report == expected_report


def test_tc560_date_not_later_than_ased_leaves_ased_untouched(synthetic):
    key = "30000000501202312"
    for record in both(synthetic, key):
        assert ased(record) == 2030105  # TC 560 date was 2029105
    for report in both_report(synthetic, key):
        assert report == []


def test_corrected_ased_is_written_as_unsigned_packed_decimal(synthetic):
    key = "30000000601202312"
    for record in both(synthetic, key):
        assert record[ASED] == bytes.fromhex("2031288f")


# --- transaction matching, skipping and counting --------------------------


def test_matched_transactions_accumulate_into_bmf_tccnt(shipped):
    key = "20000100701202606"
    for record in both(shipped, key):
        assert record[TCCNT].decode() == "006"


def test_orphan_transactions_below_the_module_key_are_skipped_uncounted(synthetic):
    """A TC 650 for EIN 100000000 precedes every module and matches none."""
    key = "30000000101202312"
    for record in both(synthetic, key):
        assert record[TCCNT].decode() == "001"


def test_module_with_no_matching_transactions_passes_through_unchanged(synthetic):
    key = "30000000201202312"
    offset = 150  # second record of the synthetic generation
    original = synthetic.modules_in[offset:offset + 150]
    for record in both(synthetic, key):
        assert record == original


def test_trailing_orphan_transactions_end_the_run_without_a_match(synthetic):
    """The last module is reached after end-of-file on the transaction file."""
    key = "30000000901202312"
    for record in both(synthetic, key):
        assert record[TCCNT].decode() == "000"
        assert record[FRZ].decode() == "        "


def test_transaction_codes_other_than_150_976_977_560_are_counted_only(shipped):
    """TC 650 falls through the EVALUATE but still bumps BMF-TCCNT."""
    key = "10000107710202306"
    for record in both(shipped, key):
        assert record[TCCNT].decode() == "002"  # one TC 150 and one TC 650
        assert record[FRZ].decode() == "        "


# --- record and report shape ---------------------------------------------


def test_report_lines_are_written_with_trailing_spaces_stripped(shipped):
    for line in shipped.report + shipped.result.report:
        assert len(line) == 90  # DRPT is 120 bytes; 30 trailing spaces dropped


def test_every_module_read_is_written_in_input_order(shipped):
    assert len(shipped.result.modules) == len(shipped.modules_in)
    assert shipped.result.counters.read == shipped.result.counters.written == 52
    keys_in = [shipped.modules_in[o:o + 17] for o in range(0, len(shipped.modules_in), 150)]
    keys_out = [shipped.result.modules[o:o + 17]
                for o in range(0, len(shipped.result.modules), 150)]
    assert keys_in == keys_out
