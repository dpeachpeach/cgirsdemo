"""Characterization tests for the PENCALC port.

Every expected value in this file was produced by running the GnuCOBOL build of
src/PENCALC.cbl (and src/DATCNV.cbl) and capturing its output files:

  fixtures/shipped/    the pipeline's shipped data/ fixtures, run end to end
  fixtures/synthetic/  a scratch-copy run over generated inputs (mksynth.py)
  fixtures/cases.json  per-module inputs and COBOL results extracted from the
                       captures above
  fixtures/datcnv_golden.csv  438 DATCNV "G" conversions captured with dcgold.cbl

Nothing here is derived from the IRM, the comments, or the rule as documented.
Tests whose names say "legacy" assert defects that the port reproduces
deliberately; the corresponding fixes are listed in the port report, not applied.
"""

from decimal import Decimal
import functools
import json

import pytest

from conftest import FIXTURES, load_dataset
import pencalc

CASES = json.loads((FIXTURES / "cases.json").read_text())


@functools.lru_cache(maxsize=None)
def dataset(name):
    return load_dataset(name)


def module_out(name, ein, mft, txpd):
    key = (ein + mft + txpd).encode()
    for raw in dataset(name)["records"]:
        if raw[0:17] == key:
            return pencalc.ModuleRecord(raw)
    raise AssertionError("no module %s" % key)


def penalties(name, ein, mft="01", txpd="202312"):
    record = module_out(name, ein, mft, txpd)
    return (
        pencalc.unpack_comp3(record.raw[record.PFTF], 2, True),
        pencalc.unpack_comp3(record.raw[record.PFTP], 2, True),
    )


def report_for(name, ein):
    return [
        line.rstrip(" ") for line in dataset(name)["report"] if line[9:18] == ein
    ]


# --------------------------------------------------------------------------
# whole-run equivalence with the captured COBOL output
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["shipped", "synthetic"])
def test_module_file_is_byte_identical_to_cobol(name):
    data = dataset(name)
    assert b"".join(data["records"]) == data["cobol_modout"]


@pytest.mark.parametrize("name", ["shipped", "synthetic"])
def test_report_is_identical_to_cobol(name):
    data = dataset(name)
    assert [line.rstrip(" ") for line in data["report"]] == data["cobol_report"]


def test_shipped_counters_match_cobol_display():
    engine = dataset("shipped")["engine"]
    assert (
        engine.read_count,
        engine.written_count,
        engine.ftf_count,
        engine.minimum_count,
    ) == (52, 52, 25, 3)


def test_synthetic_counters_match_cobol_display():
    engine = dataset("synthetic")["engine"]
    assert (
        engine.read_count,
        engine.written_count,
        engine.ftf_count,
        engine.minimum_count,
    ) == (64, 64, 32, 8)


# --------------------------------------------------------------------------
# per-module characterization, one test per module in each captured run
# --------------------------------------------------------------------------


def _case_params(name):
    return [
        pytest.param(name, case, id="%s-%s-%s-%s" % (name, case["ein"], case["mft"], case["txpd"]))
        for case in CASES[name]
    ]


@pytest.mark.parametrize(
    "name,case", _case_params("shipped") + _case_params("synthetic")
)
def test_module_penalties_match_cobol(name, case):
    ftf, ftp = penalties(name, case["ein"], case["mft"], case["txpd"])
    assert ftf == Decimal(case["expected_pftf"])
    assert ftp == Decimal(case["expected_pftp"])
    lines = [
        line
        for line in dataset(name)["report"]
        if line[9:18] == case["ein"]
        and line[19:21] == case["mft"]
        and line[22:28] == case["txpd"]
    ]
    assert [line.rstrip(" ") for line in lines] == case["expected_report"]


# --------------------------------------------------------------------------
# DATCNV, captured with a COBOL driver calling the shipped shim
# --------------------------------------------------------------------------

DATCNV_GOLDEN = [
    tuple(line.split(","))
    for line in (FIXTURES / "datcnv_golden.csv").read_text().splitlines()
    if line.strip()
]


@pytest.mark.parametrize("julian,greg,rc", DATCNV_GOLDEN, ids=[g[0] for g in DATCNV_GOLDEN])
def test_datcnv_julian_to_gregorian_matches_cobol(julian, greg, rc):
    result = pencalc.datcnv_to_gregorian(int(julian))
    if rc == "8":
        assert result is None, "COBOL rejected %s with RC 8" % julian
    else:
        assert result == int(greg)


# --------------------------------------------------------------------------
# branch-level behaviour, each anchored to a captured module
# --------------------------------------------------------------------------


def test_no_tc150_leaves_penalties_untouched():
    """990000011 has only a TC 650, so D150 stays zero and 2200-MONTHS exits."""
    assert penalties("synthetic", "990000011") == (Decimal("0.00"), Decimal("0.00"))
    assert report_for("synthetic", "990000011") == []


def test_no_transactions_at_end_of_file():
    """990000090 is the highest key and is reached after TEOF."""
    assert penalties("synthetic", "990000090") == (Decimal("0.00"), Decimal("0.00"))
    assert report_for("synthetic", "990000090") == []


def test_filed_before_due_date_assesses_nothing():
    """990000021 filed 2024-010, before the 2024-01-15 due date: WDLD < 1."""
    assert penalties("synthetic", "990000021") == (Decimal("0.00"), Decimal("0.00"))


def test_two_months_delinquent_ftf_and_ftp():
    """990000031: 10000.00 unpaid, 2 months -> 5% and 0.5% per month."""
    assert penalties("synthetic", "990000031") == (Decimal("900.00"), Decimal("100.00"))
    assert report_for("synthetic", "990000031") == [
        "PENCALC  990000031 01 202312  P501  FTF/FTP ASSESSED            2"
        "     900.00     100.00"
    ]


def test_legacy_last_tc150_wins_over_earliest():
    """990000085 carries TC 150 on 2024-046 and 2024-200; the loop keeps the
    last one read, so the later filing date drives the delinquency."""
    assert penalties("synthetic", "990000085") == (
        Decimal("2150.00"),
        Decimal("350.00"),
    )


def test_invalid_julian_day_yields_no_penalty():
    """990000061 files on Julian day 400: DATCNV returns RC 8 and leaves
    DCP-GREG zero, so INTEGER-OF-DATE(0) makes the module look timely."""
    assert penalties("synthetic", "990000061") == (Decimal("0.00"), Decimal("0.00"))


def test_legacy_minimum_penalty_can_store_a_negative_ftf():
    """990000041: FTF and FTP both cap at 18750.00, the offset drives FTF to
    zero, and 2600-MIN then computes 485.00 - 18750.00 with no zero floor."""
    ftf, ftp = penalties("synthetic", "990000041", txpd="201812")
    assert ftf == Decimal("-18265.00")
    assert ftp == Decimal("18750.00")


def test_legacy_report_prints_negative_ftf_without_a_sign():
    """The same module reports 18265.00 because PR-FTF is an unsigned edit."""
    assert report_for("synthetic", "990000041") == [
        "PENCALC  990000041 01 201812  P502  MINIMUM FTF APPLIED        66"
        "   18265.00   18750.00",
        "PENCALC  990000041 01 201812  P501  FTF/FTP ASSESSED           66"
        "   18265.00   18750.00",
    ]


def test_minimum_penalty_is_capped_at_the_unpaid_balance():
    """990000051 owes 0.01, so WMIN collapses to the balance."""
    assert penalties("synthetic", "990000051") == (Decimal("0.01"), Decimal("0.00"))
    assert "P502  MINIMUM FTF APPLIED" in report_for("synthetic", "990000051")[0]


def test_century_year_2100_is_not_a_leap_year():
    """990000071 files on 2100-200; DATCNV's 3000-LEAP excludes 2100."""
    assert pencalc.datcnv_to_gregorian(2100200) == 21000719
    assert penalties("synthetic", "990000071") == (
        Decimal("-265.00"),
        Decimal("750.00"),
    )


def test_year_2000_is_a_leap_year():
    """990000081 files on 2000-200, before its due date, so nothing is due, but
    the conversion itself exercises the divisible-by-400 restoration."""
    assert pencalc.datcnv_to_gregorian(2000200) == 20000718
    assert penalties("synthetic", "990000081") == (Decimal("0.00"), Decimal("0.00"))


def test_legacy_penalty_field_overflows_silently():
    """990000087 owes 99999999999.99. The 25% caps exceed S9(9)V99, so the
    stored penalties keep only the low-order digits and the report loses two
    more digits to the ZZZZZZ9.99 edit."""
    ftf, ftp = penalties("synthetic", "990000087")
    assert ftf == Decimal("-999999514.99")
    assert ftp == Decimal("999999999.99")
    assert report_for("synthetic", "990000087") == [
        "PENCALC  990000087 01 202312  P502  MINIMUM FTF APPLIED         6"
        " 9999514.99 9999999.99",
        "PENCALC  990000087 01 202312  P501  FTF/FTP ASSESSED            6"
        " 9999514.99 9999999.99",
    ]


def test_orphan_transactions_are_skipped():
    """The synthetic run carries a transaction whose key precedes every module;
    the 2100-PEN skip loop consumes it and no module is affected."""
    keys = {case["ein"] for case in CASES["synthetic"]}
    transactions = pencalc.read_fixed(
        FIXTURES / "synthetic" / "TRANIN.dat",
        pencalc.TRN_LRECL,
        pencalc.TransactionRecord,
    )
    orphans = {
        trn.raw[0:9].decode() for trn in transactions if trn.raw[0:9].decode() not in keys
    }
    assert orphans
    data = dataset("synthetic")
    assert b"".join(data["records"]) == data["cobol_modout"]


def test_negative_unpaid_balance_is_floored_at_zero():
    """Shipped module 200001022 has credits exceeding assessments."""
    negatives = [
        case
        for case in CASES["shipped"] + CASES["synthetic"]
        if Decimal(case["assd"]) - Decimal(case["dep"]) - Decimal(case["crd"]) < 0
    ]
    assert negatives, "expected at least one over-credited module in the captures"
    for case in negatives:
        assert case["expected_report"] == []


# --------------------------------------------------------------------------
# field encoding primitives
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,digits,scale,signed,expected",
    [
        (Decimal("0.00"), 11, 2, True, "00000000000c"),
        (Decimal("-18265.00"), 11, 2, True, "00001826500d"),
        (Decimal("999999999.99"), 11, 2, True, "99999999999c"),
        (Decimal("2024167"), 7, 0, False, "2024167f"),
    ],
)
def test_comp3_round_trip(value, digits, scale, signed, expected):
    raw = pencalc.pack_comp3(value, digits, scale, signed)
    assert raw.hex() == expected
    assert pencalc.unpack_comp3(raw, scale, signed) == value


def test_comp3_store_truncates_toward_zero():
    assert pencalc.store(Decimal("1.999"), 11, 2) == Decimal("1.99")
    assert pencalc.store(Decimal("-1.999"), 11, 2) == Decimal("-1.99")


def test_wmol_uses_integer_division_of_days_by_thirty():
    """WMOL is S9(3) COMP, so (WDLD / 30) + 1 truncates."""
    engine = pencalc.Pencalc()
    engine.d150 = 2024046
    module = pencalc.ModuleRecord(dataset("synthetic")["records"][0])
    module.raw[module.TXPD] = b"202312"
    engine._months(module)
    assert engine.wdld == 31
    assert engine.wmol == 2
