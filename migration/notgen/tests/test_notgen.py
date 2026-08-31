"""Characterization tests for the NOTGEN port.

Every expected value in this file comes from an actual GnuCOBOL run of
src/NOTGEN.cbl. The captures live in migration/notgen/fixtures/<set>/ as
(MODOFF.dat, NOTICE.dat, NOTGEN.rpt, counters.txt) golden quadruples:

  shipped              the pipeline's own data/MODOFF.dat after run/pipeline.sh
  synthetic_selection  24 constructed records covering the selection branches
                       the shipped fixtures never reach
  synthetic_edge       10 constructed records covering sign nibbles, field
                       overflow and edit-picture truncation
  sign_nibbles         one record per COMP-3 sign nibble 0x0-0xF

Tests assert current behaviour, defects included; defect assertions are named
for the defect.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import notgen  # noqa: E402

FIXTURES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures"
)
SETS = ["shipped", "synthetic_selection", "synthetic_edge", "sign_nibbles"]


def fixture_path(name, filename):
    return os.path.join(FIXTURES, name, filename)


def run_port(name):
    records = notgen.read_module_file(fixture_path(name, "MODOFF.dat"))
    return notgen.process(records)


def golden_notice(name):
    with open(fixture_path(name, "NOTICE.dat"), "rb") as handle:
        return handle.read()


def golden_report(name):
    with open(fixture_path(name, "NOTGEN.rpt"), encoding="latin-1") as handle:
        return handle.read().splitlines()


def golden_counters(name):
    with open(fixture_path(name, "counters.txt"), encoding="latin-1") as handle:
        return handle.read().splitlines()


def report_line_for(name, ein):
    lines = [line for line in golden_report(name) if line[8:17] == ein]
    assert len(lines) <= 1, "more than one report line for %s" % ein
    return lines[0] if lines else None


def port_report_line_for(name, ein):
    _notices, report, _counters = run_port(name)
    lines = [line.rstrip(" ") for line in report if line[8:17] == ein]
    return lines[0] if lines else None


# --- golden pairs: whole-file equivalence -----------------------------------


@pytest.mark.parametrize("name", SETS)
def test_notice_file_is_byte_identical_to_cobol(name):
    notices, _report, _counters = run_port(name)
    assert b"".join(notices) == golden_notice(name)


@pytest.mark.parametrize("name", SETS)
def test_report_file_matches_cobol_line_for_line(name):
    _notices, report, _counters = run_port(name)
    assert [line.rstrip(" ") for line in report] == golden_report(name)


@pytest.mark.parametrize("name", SETS)
def test_display_counters_match_cobol(name):
    _notices, _report, counters = run_port(name)
    produced = [
        "NOTGEN  READ    %06d" % counters.read,
        "NOTGEN  NOTICES %06d" % counters.notices,
        "NOTGEN  SUPPRESS%06d" % counters.suppressed,
    ]
    assert produced == golden_counters(name)


def test_shipped_fixture_counts_are_the_pipeline_numbers():
    assert golden_counters("shipped") == [
        "NOTGEN  READ    000052",
        "NOTGEN  NOTICES 000045",
        "NOTGEN  SUPPRESS000003",
    ]


# --- selection order (EVALUATE TRUE in 2100-SEL) ----------------------------


def test_freeze_a_outranks_every_other_selection_reason():
    # 900000024 carries freeze A and freeze R with a -6000.00 balance; the
    # COBOL reports CP 0193 severity 3, not the 0267 the balance would give.
    line = report_line_for("synthetic_selection", "900000024")
    assert line[29:33] == "0193"
    assert line.endswith("3")
    assert port_report_line_for("synthetic_selection", "900000024") == line


def test_ftd_penalty_outranks_civil_penalty_when_both_are_positive():
    line = report_line_for("synthetic_selection", "900000010")
    assert line[29:33] == "0194"
    assert "POSSIBLE FTD PENALTY" in line
    assert port_report_line_for("synthetic_selection", "900000010") == line


def test_civil_penalty_selected_when_only_ftf_is_positive():
    line = report_line_for("synthetic_selection", "900000011")
    assert line[29:33] == "0215"
    assert port_report_line_for("synthetic_selection", "900000011") == line


def test_negative_ftd_penalty_does_not_select_cp_0194():
    # PIC S9(9)V99 holding -250.00 fails "> ZERO"; the record falls through to
    # the balance test and the COBOL emits CP 0161.
    line = report_line_for("synthetic_selection", "900000012")
    assert line[29:33] == "0161"
    assert port_report_line_for("synthetic_selection", "900000012") == line


def test_balance_due_threshold_is_strictly_above_one_hundred():
    assert report_line_for("synthetic_selection", "900000002") is None  # exactly 100.00
    plus = report_line_for("synthetic_selection", "900000003")  # 100.01
    assert plus[29:33] == "0161"
    assert port_report_line_for("synthetic_selection", "900000002") is None
    assert port_report_line_for("synthetic_selection", "900000003") == plus


def test_overpayment_threshold_is_strictly_below_minus_one_hundred():
    assert report_line_for("synthetic_selection", "900000004") is None  # -100.00
    minus = report_line_for("synthetic_selection", "900000005")  # -100.01
    assert minus[29:33] == "0267"
    assert port_report_line_for("synthetic_selection", "900000004") is None
    assert port_report_line_for("synthetic_selection", "900000005") == minus


def test_unselected_module_produces_neither_notice_nor_report_line():
    assert report_line_for("synthetic_selection", "900000013") is None
    assert port_report_line_for("synthetic_selection", "900000013") is None
    assert b"900000013" not in golden_notice("synthetic_selection")
    notices, _report, _counters = run_port("synthetic_selection")
    assert all(not notice.startswith(b"900000013") for notice in notices)


def test_lowercase_a_in_freeze_byte_is_not_the_duplicate_return_freeze():
    line = report_line_for("synthetic_selection", "900000018")
    assert line[29:33] == "0161"
    assert port_report_line_for("synthetic_selection", "900000018") == line


# --- suppression (2100-SEL freeze tests) ------------------------------------


def test_refund_freeze_suppresses_overpayment_notice_only():
    suppressed = report_line_for("synthetic_selection", "900000006")  # 0267 + R
    assert "SUPPRESSED BY FREEZE" in suppressed
    kept = report_line_for("synthetic_selection", "900000008")  # 0161 + R
    assert "BALANCE DUE" in kept
    assert port_report_line_for("synthetic_selection", "900000006") == suppressed
    assert port_report_line_for("synthetic_selection", "900000008") == kept


def test_z_freeze_suppresses_notices_of_every_class():
    line = report_line_for("synthetic_selection", "900000009")  # freeze A + Z
    assert line[29:33] == "0193"
    assert "SUPPRESSED BY FREEZE" in line
    assert port_report_line_for("synthetic_selection", "900000009") == line


def test_suppressed_record_keeps_its_cp_code_and_amount_on_the_report():
    line = report_line_for("synthetic_selection", "900000020")  # 0267 + R + Z
    assert line[29:33] == "0267"
    assert "9000.00-" in line
    assert port_report_line_for("synthetic_selection", "900000020") == line


def test_suppressed_record_writes_no_notice_record():
    notices, _report, counters = run_port("synthetic_selection")
    joined = b"".join(notices)
    for ein in (b"900000006", b"900000007", b"900000009", b"900000020"):
        assert ein not in joined
    assert counters.suppressed == 4


def test_z_freeze_on_an_unselected_module_produces_nothing():
    assert report_line_for("synthetic_edge", "910000008") is None
    assert port_report_line_for("synthetic_edge", "910000008") is None


# --- arithmetic and picture editing -----------------------------------------


def test_report_amount_silently_truncates_high_order_digits():
    # Legacy defect: WBAL is PIC S9(11)V99 but NR-AMT is ZZZZZZZZ9.99-, so a
    # 12,345,678,901.23 balance prints as 345678901.23. Proposed fix logged,
    # not applied.
    line = report_line_for("synthetic_selection", "900000014")
    assert "345678901.23" in line
    assert port_report_line_for("synthetic_selection", "900000014") == line


def test_notice_record_keeps_the_full_amount_the_report_truncates():
    notices, _report, _counters = run_port("synthetic_selection")
    notice = next(n for n in notices if n.startswith(b"900000014"))
    golden = next(
        golden_notice("synthetic_selection")[offset : offset + 100]
        for offset in range(0, len(golden_notice("synthetic_selection")), 100)
        if golden_notice("synthetic_selection")[offset : offset + 9] == b"900000014"
    )
    assert notice == golden
    assert notgen.unpack_comp3(golden[60:67], 2) == notgen.Decimal("12345678901.23")


def test_balance_wraps_at_eleven_integer_digits_with_no_size_error():
    # Legacy defect: COMPUTE has no ON SIZE ERROR, so 100,999,999,999.98
    # becomes 999,999,999.98 in WBAL.
    line = report_line_for("synthetic_selection", "900000017")
    assert "999999999.98" in line
    assert port_report_line_for("synthetic_selection", "900000017") == line


def test_intermediate_liability_field_wraps_before_the_balance_is_computed():
    line = report_line_for("synthetic_edge", "910000004")
    assert "999999999.96" in line
    assert port_report_line_for("synthetic_edge", "910000004") == line


def test_credits_and_interest_reduce_the_balance():
    line = report_line_for("synthetic_selection", "900000021")
    assert "1000.00-" in line
    assert port_report_line_for("synthetic_selection", "900000021") == line


def test_negative_interest_increases_the_balance():
    line = report_line_for("synthetic_edge", "910000009")
    assert line[29:33] == "0161"
    assert "2500.00" in line
    assert port_report_line_for("synthetic_edge", "910000009") == line


def test_zero_balance_prints_as_zero_with_a_trailing_blank_sign():
    line = report_line_for("shipped", "120001322")
    assert line[29:33] == "0193"
    assert line.endswith("0.00   3")
    assert port_report_line_for("shipped", "120001322") == line


# --- COMP-3 sign handling ----------------------------------------------------


def test_only_sign_nibble_d_reads_as_negative():
    # Acceptable Difference candidate: the IBM encoding also treats 0xB as
    # negative. This runtime does not, and the port follows the runtime.
    report = golden_report("sign_nibbles")
    negative = [line[8:17] for line in report if line.rstrip().endswith("-  1")]
    assert negative == ["920000013"]
    _notices, port_lines, _counters = run_port("sign_nibbles")
    assert [line.rstrip(" ") for line in port_lines] == report


def test_sign_nibble_b_on_a_penalty_field_selects_cp_0194():
    line = report_line_for("synthetic_edge", "910000002")
    assert line[29:33] == "0194"
    assert port_report_line_for("synthetic_edge", "910000002") == line


def test_unsigned_sign_nibble_f_reads_as_positive():
    line = report_line_for("synthetic_edge", "910000001")
    assert "7250.00" in line
    assert port_report_line_for("synthetic_edge", "910000001") == line


def test_notice_amount_is_written_with_c_or_d_sign_nibbles():
    data = golden_notice("shipped")
    signs = {data[offset + 66] & 0x0F for offset in range(0, len(data), 100)}
    assert signs == {0x0C, 0x0D}
    notices, _report, _counters = run_port("shipped")
    assert {notice[66] & 0x0F for notice in notices} == signs


# --- record layout and the hard-coded notice date ---------------------------


def test_notice_record_layout_matches_the_copybook_offsets():
    data = golden_notice("shipped")
    assert len(data) % notgen.NOTICE_RECORD_LEN == 0
    first = data[:100]
    records = notgen.read_module_file(fixture_path("shipped", "MODOFF.dat"))
    module = records[0]
    assert first[0:9].decode() == module.ein
    assert first[9:11].decode() == module.mft
    assert first[11:17].decode() == module.txpd
    assert first[21:25].decode() == module.nctl
    assert first[25:60].decode() == module.name
    assert first[74:75] == b"1"
    assert first[75:100] == b" " * 25


def test_notice_date_is_the_hardcoded_business_day_shifted_julian():
    # 2200-BLD hard-codes 20260815 (a Saturday); DATECNV shifts it to Monday
    # 2026-08-17 and the notice carries julian 2026229 on every record.
    data = golden_notice("shipped")
    dates = {data[offset + 67 : offset + 74] for offset in range(0, len(data), 100)}
    assert dates == {b"2026229"}
    assert notgen.datecnv_business_day(notgen.NOTICE_DATE_GREG)[1] == 2026229


def test_every_module_read_is_counted_including_unselected_ones():
    _notices, _report, counters = run_port("synthetic_selection")
    module_count = len(
        notgen.read_module_file(fixture_path("synthetic_selection", "MODOFF.dat"))
    )
    assert counters.read == module_count == 24
    assert counters.notices == 16
