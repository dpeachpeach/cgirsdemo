"""Per-branch characterization of 2100-FRZ.

Each expected value is read out of the COBOL-captured golden files (the
MODFRZ.dat record and the FRZEVAL.rpt line the legacy program produced for
that EIN), so no assertion here encodes the rule as a human reads it.
"""

import pytest

from conftest import run_one

# EIN -> the freeze combination it carries in the fixtures.
A_ONLY = "120001322"
Z_ONLY = "200001329"
L_ONLY = "470001364"
S_ONLY = "910001189"
V_ONLY = "910001273"
ALL_BUT_A = "200001007"
HUGE_BALANCE_A = "990001001"
NEGATIVE_PENNY_V = "990001002"
PRESET_R_AND_O = "990001003"
X_ONLY = "990001004"
ALL_FREEZES_OVERFLOW = "990001005"


@pytest.mark.parametrize(
    "ein, fixture",
    [
        (A_ONLY, "shipped"),
        (Z_ONLY, "shipped"),
        (L_ONLY, "shipped"),
        (S_ONLY, "shipped"),
        (V_ONLY, "shipped"),
        (ALL_BUT_A, "shipped"),
        (HUGE_BALANCE_A, "synthetic"),
        (NEGATIVE_PENNY_V, "synthetic"),
        (PRESET_R_AND_O, "synthetic"),
        (X_ONLY, "synthetic"),
        (ALL_FREEZES_OVERFLOW, "synthetic"),
    ],
)
def test_record_and_report_match_cobol_for_each_freeze_combination(
    ein, fixture, request
):
    golden = request.getfixturevalue(fixture)
    record, report_line, _ = run_one(golden.record_for(ein))
    assert record == golden.expected_record_for(ein)
    assert [line for line in [report_line] if line] == golden.expected_report_for(ein)


def test_a_freeze_suppresses_refund_only(shipped):
    record, line, counters = run_one(shipped.record_for(A_ONLY))
    assert record[58:66].decode() == "A  R    "
    assert "REFUND SUPPRESSED" in line
    assert (counters.refund_suppressed, counters.offset_suppressed) == (1, 0)


def test_s_freeze_suppresses_refund_only(shipped):
    record, line, counters = run_one(shipped.record_for(S_ONLY))
    assert record[58:66].decode() == "   RS   "
    assert "REFUND SUPPRESSED" in line
    assert (counters.refund_suppressed, counters.offset_suppressed) == (1, 0)


def test_v_freeze_suppresses_offset_only(shipped):
    record, line, counters = run_one(shipped.record_for(V_ONLY))
    assert record[58:66].decode() == " V     O"
    assert "OFFSET SUPPRESSED" in line
    assert (counters.refund_suppressed, counters.offset_suppressed) == (0, 1)


@pytest.mark.parametrize("ein", [L_ONLY, Z_ONLY])
def test_l_and_z_freezes_each_suppress_both_refund_and_offset(ein, shipped):
    record, line, counters = run_one(shipped.record_for(ein))
    assert record[61:62] == b"R" and record[65:66] == b"O"
    assert "REFUND AND OFFSET SUPPRESSED" in line
    assert (counters.refund_suppressed, counters.offset_suppressed) == (1, 1)


def test_x_freeze_code_is_ignored_entirely(synthetic):
    record, line, counters = run_one(synthetic.record_for(X_ONLY))
    assert record[58:66].decode() == "     X  "
    assert line is None
    assert (counters.refund_suppressed, counters.offset_suppressed) == (0, 0)


def test_preexisting_r_and_o_are_kept_but_not_counted_or_reported(synthetic):
    """No freeze code is present, so WFZC stays zero: the program neither
    clears the R/O positions it finds nor counts or reports them."""
    record, line, counters = run_one(synthetic.record_for(PRESET_R_AND_O))
    assert record[58:66].decode() == "   R   O"
    assert line is None
    assert (counters.refund_suppressed, counters.offset_suppressed) == (0, 0)


def test_records_without_any_freeze_code_produce_no_report_line(shipped):
    unfrozen = [
        record
        for record in shipped.records
        if record[58:59] != b"A"
        and record[59:60] != b"V"
        and record[60:61] != b"L"
        and record[62:63] != b"S"
        and record[64:65] != b"Z"
    ]
    assert unfrozen, "fixture should contain unfrozen modules"
    for record in unfrozen:
        result, line, counters = run_one(record)
        assert result == record
        assert line is None
        assert (counters.refund_suppressed, counters.offset_suppressed) == (0, 0)


def test_reported_freeze_string_includes_the_r_and_o_set_by_this_run(shipped):
    _, line, _ = run_one(shipped.record_for(ALL_BUT_A))
    assert line[68:76] == " VLRS ZO"
