"""Branch coverage of the frozen fixtures against pencalc.BRANCHES."""

import pencalc

SHIPPED_ONLY_UNCOVERED = {
    "B03", "B05", "B15", "B19", "B23", "B26", "B27",
    "B30", "B37", "B39", "B40", "B46", "B47", "B48",
}

# B37/B39 need a DATCNV function code PENCALC never passes; B48 needs a Julian
# day that 2000-GREG has already rejected. Covered by the DATCNV harness
# goldens (B37/B39) or unreachable (B48).
UNREACHABLE_FROM_PENCALC = {"B37", "B39", "B48"}


def test_branch_catalogue_is_contiguous():
    assert list(pencalc.BRANCHES) == [f"B{i:02d}" for i in range(1, 49)]


def test_shipped_fixture_coverage_is_the_reported_number(shipped):
    hit = shipped.result.branches
    assert set(pencalc.BRANCHES) - hit == SHIPPED_ONLY_UNCOVERED
    assert len(hit) == 34


def test_synthetic_fixtures_close_the_reachable_gap(synthetic):
    hit = synthetic.result.branches
    assert set(pencalc.BRANCHES) - hit == UNREACHABLE_FROM_PENCALC
    assert len(hit) == 45


def test_datcnv_only_branches_are_covered_by_the_harness_goldens():
    hits: set = set()
    pencalc.datcnv("J", greg=20240410, hits=hits)
    pencalc.datcnv("X", greg=20240410, hits=hits)
    assert {"B37", "B39"} <= hits
