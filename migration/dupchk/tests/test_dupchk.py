"""Characterization tests for the DUPCHK port.

Every expected value in this file was captured by running the COBOL
(`bin/DUPCHK`, GnuCOBOL 3.1.2) over the fixture inputs stored beside it; the
frozen COBOL outputs live in `fixtures/<scenario>/`. Nothing here is derived
from IRM 21.7.9 or from what the rule ought to be. Tests whose names call out a
defect assert legacy behaviour on purpose.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dupchk import MOD_LRECL, comp3_to_int, process  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SCENARIOS = ("baseline", "synthetic")


def load(scenario):
    d = FIXTURES / scenario
    return ((d / "BMFMOD.dat").read_bytes(), (d / "TRANIN.dat").read_bytes())


def golden(scenario):
    d = FIXTURES / scenario
    return (
        (d / "MODDUP.dat").read_bytes(),
        (d / "DUPCHK.rpt").read_text(),
        (d / "stdout.txt").read_text(),
    )


def run(scenario):
    mod_in, trn_in = load(scenario)
    return process(mod_in, trn_in)


def records(blob):
    return [blob[i:i + MOD_LRECL] for i in range(0, len(blob), MOD_LRECL)]


def module(blob, key):
    for rec in records(blob):
        if rec[0:17] == key:
            return rec
    raise AssertionError(f"module {key!r} not in output")


# --- golden-pair equivalence -------------------------------------------------

@pytest.mark.parametrize("scenario", SCENARIOS)
def test_module_output_file_is_byte_identical_to_cobol(scenario):
    assert run(scenario).mod_out == golden(scenario)[0]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_report_file_is_byte_identical_to_cobol(scenario):
    assert run(scenario).report == golden(scenario)[1]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_end_of_job_counters_match_cobol_display(scenario):
    expected = golden(scenario)[2].splitlines()
    assert run(scenario).counters.display_lines() == expected


# --- baseline fixture behaviour ---------------------------------------------

def test_baseline_sets_three_a_freezes_and_three_ased_corrections():
    counters = run("baseline").counters
    assert (counters.read, counters.written) == (52, 52)
    assert counters.a_freeze == 3
    assert counters.ased_corrected == 3


def test_a_freeze_writes_letter_a_into_first_freeze_byte():
    out = run("baseline").mod_out
    rec = module(out, b"120001322" + b"01" + b"202303")
    assert rec[58:59] == b"A"
    assert rec[59:66] == b" " * 7


def test_tc560_later_than_ased_replaces_packed_ased_field():
    out = run("baseline").mod_out
    rec = module(out, b"200001007" + b"01" + b"202606")
    assert comp3_to_int(rec[66:70]) == 2031288


def test_report_columns_hold_c76_c77_and_last_tc976_date():
    line = run("baseline").report.splitlines()[0]
    assert line.startswith("DUPCHK  120001322 01 202303  D201  ")
    assert line.endswith("001 000 2024146")


def test_d202_line_reports_the_tc560_date_and_zeroed_counts():
    lines = [l for l in run("baseline").report.splitlines() if "D202" in l]
    assert lines[0].endswith("000 000 2031288")
    assert "TC 560 ASED CORRECTION APPLIED" in lines[0]


# --- legacy defects, reproduced on purpose ----------------------------------

def test_tc560_in_same_module_cancels_the_duplicate_freeze():
    """C76>0 AND C60>0 clears DUPSW unconditionally (2400-EVAL, third IF).

    A module with TC 150 + TC 976 is a duplicate filing, but any TC 560 in the
    same module suppresses the -A freeze. Three baseline modules qualify as
    duplicates through the C76 leg and never get frozen.
    """
    out = run("baseline").mod_out
    rec = module(out, b"200001007" + b"01" + b"202606")
    assert rec[58:59] == b" "  # duplicate candidate, no freeze
    assert comp3_to_int(rec[66:70]) == 2031288  # but the ASED was corrected


def test_multiple_tc150_freeze_is_also_cancelled_by_a_tc976_plus_tc560():
    """The DUPSW reset is not qualified by the C50>1 test that precedes it, so
    even an unambiguous multiple-filing condition can be cleared."""
    from dupchk import process as _process
    mod_in, trn_in = load("baseline")
    result = _process(mod_in, trn_in)
    frozen = [r[0:17] for r in records(result.mod_out) if r[58:59] == b"A"]
    assert len(frozen) == 3


def test_dup_report_shows_zero_tc976_date_when_duplicate_came_from_tc977():
    """DR-C is always D76, so a TC 150 + TC 977 duplicate reports 0000000
    rather than the TC 977 date."""
    line = [l for l in run("synthetic").report.splitlines()
            if l.startswith("DUPCHK  700000001")][0]
    assert line.endswith("000 001 0000000")


def test_multiple_tc150_report_line_carries_no_transaction_date_at_all():
    line = [l for l in run("synthetic").report.splitlines()
            if l.startswith("DUPCHK  700000002")][0]
    assert line.endswith("000 000 0000000")


def test_tccnt_wraps_silently_past_999_because_pic_is_three_digits():
    """BMF-TCCNT is PIC 9(3) and 2300-GATHER adds to it with no ON SIZE ERROR.
    The synthetic module starts at 998 and takes two transactions."""
    out = run("synthetic").mod_out
    rec = module(out, b"700000002" + b"01" + b"202312")
    assert rec[131:134] == b"000"


def test_tccnt_counts_transactions_the_evaluate_ignores():
    """The counter is bumped for every matched transaction, including TCs with
    no WHEN branch (the synthetic module has a TC 290)."""
    out = run("synthetic").mod_out
    rec = module(out, b"700000001" + b"01" + b"202312")
    assert rec[131:134] == b"008"  # started at 005, three transactions matched


def test_transactions_below_the_module_key_are_dropped_without_a_reject():
    """2200-SKIP consumes orphan transactions and tallies nothing; the
    DUPCHK.REJECTS dataset the JCL allocates is never written."""
    result = run("synthetic")
    assert "600000000" not in result.report
    assert result.counters.read == 4


def test_tc560_not_later_than_ased_leaves_the_ased_untouched():
    out = run("synthetic").mod_out
    rec = module(out, b"700000003" + b"01" + b"202312")
    assert comp3_to_int(rec[66:70]) == 2030105
    assert "700000003" not in run("synthetic").report


def test_module_after_transaction_eof_is_written_unchanged():
    out = run("synthetic").mod_out
    rec = module(out, b"700000004" + b"01" + b"202312")
    assert rec[58:59] == b" "
    assert rec[131:134] == b"000"


def test_every_input_module_is_written_even_when_nothing_matches():
    for scenario in SCENARIOS:
        mod_in, _ = load(scenario)
        result = run(scenario)
        assert len(result.mod_out) == len(mod_in)
