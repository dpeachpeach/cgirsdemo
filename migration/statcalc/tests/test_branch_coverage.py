"""Branch inventory, so the coverage numbers in the port report are reproducible.

Branch IDs are the ones recorded by `statcalc.Trace`: S* in STATCALC,
D* in the DATCNV shim it calls.
"""

from helpers import Run

STATCALC_BRANCHES = [
    "S1",  # 2000-PROC READ AT END (PERFORM UNTIL EOFSW exit)
    "S2",  # 2000-PROC READ NOT AT END
    "S3",  # 2200-RDD EVALUATE BMF-MFT WHEN 01
    "S4",  # MFT 01, SM > 12 after ADD 1
    "S5",  # MFT 01, SM not > 12
    "S6",  # WHEN 02
    "S7",  # MFT 02, SM > 12 after ADD 4
    "S8",  # MFT 02, SM not > 12
    "S9",  # WHEN OTHER
    "S11",  # 2350-SPCL EVALUATE SCC WHEN 07
    "S12",  # WHEN 12
    "S13",  # neither (implicit WHEN OTHER)
    "S14",  # 2400-RSED BMF-DEP > ZERO
    "S15",  # BMF-DEP not > ZERO
    "S16",  # (W7YR * 1000) > W7RS
    "S17",  # not >
    "S18V",  # 2500-CSED BMF-FRZ-V = "V"
    "S18Z",  # BMF-FRZ-Z = "Z"
    "S19",  # neither freeze
    "S20",  # suspended CSED day-of-year > 365
    "S21",  # not > 365
]

DATCNV_BRANCHES = [
    "D1",  # DCP-FUNC = "J"
    "D2",  # DCP-FUNC = "G"
    "D3",  # DCP-FUNC neither -> RC 8
    "D4",  # 1000-TOJUL month/day out of range -> RC 8
    "D5",  # 1000-TOJUL in range
    "D6",  # 2000-TOGRG day-of-year out of range -> RC 8
    "D7",  # 2000-TOGRG month found (GO TO 2000-BLD)
    "D8",  # 2000-TOGRG month loop exhausted
    "D9",  # 2000-TOGRG February leap adjustment
    "D10",  # 1000-TOJUL February leap adjustment
    "D11",  # 3000-LEAP year not divisible by 4
    "D12",  # divisible by 4, not by 100
    "D13",  # divisible by 100, not by 400
    "D14",  # divisible by 400
]

ALL_BRANCHES = STATCALC_BRANCHES + DATCNV_BRANCHES

# Provably unreachable from STATCALC: S16 is arithmetically impossible, and the
# Gregorian direction of DATCNV is never requested by this caller.
UNREACHABLE = {"S16", "D2", "D3", "D6", "D7", "D8", "D9"}


def test_branch_inventory_is_35_branches():
    assert len(ALL_BRANCHES) == 35


def test_shipped_fixtures_cover_25_of_35_branches():
    hits = Run("shipped").job.trace.hits
    covered = {b for b in ALL_BRANCHES if hits.get(b)}
    assert len(covered) == 25
    assert set(ALL_BRANCHES) - covered == UNREACHABLE | {"D13", "D14", "D4"}


def test_synthetic_fixtures_cover_every_reachable_branch():
    hits = Run("synthetic").job.trace.hits
    covered = {b for b in ALL_BRANCHES if hits.get(b)}
    assert set(ALL_BRANCHES) - covered == UNREACHABLE
    assert len(covered) == 28
