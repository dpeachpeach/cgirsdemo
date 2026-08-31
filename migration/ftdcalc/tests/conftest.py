"""Golden-pair loading for the FTDCALC characterization suite.

Every expected value used by these tests comes out of a file in
migration/ftdcalc/fixtures/, and every one of those files is a capture of an
actual GnuCOBOL run of src/FTDCALC.cbl.  See fixtures/PROVENANCE.md.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))

import ftdcalc  # noqa: E402


@dataclass(frozen=True)
class GoldenPair:
    """One captured COBOL run: its inputs, its outputs, its DISPLAY counters."""

    name: str
    modin: bytes
    trnin: bytes
    modout: bytes
    report: list[str]
    counters: dict[str, int]

    def run(self) -> ftdcalc.Result:
        return ftdcalc.run(self.modin, self.trnin)


def _counters(path: Path) -> dict[str, int]:
    keys = {
        "READ": "read",
        "WRITTEN": "written",
        "PENALTY": "penalty",
        "DEMINIM": "deminimis",
        "BYPASS": "bypass",
    }
    out = {}
    for line in path.read_text().splitlines():
        _, label, value = line.split(None, 2)
        out[keys[label]] = int(value)
    return out


def _load(name: str, modin_dir: str) -> GoldenPair:
    here = FIXTURES / name
    return GoldenPair(
        name=name,
        modin=(FIXTURES / modin_dir / "MODSTAT.dat").read_bytes(),
        trnin=(here / "TRANIN.dat").read_bytes(),
        modout=(here / "MODFTD.dat").read_bytes(),
        report=(here / "FTDCALC.rpt").read_text().splitlines(),
        counters=_counters(here / "counters.txt"),
    )


@pytest.fixture(scope="session")
def shipped() -> GoldenPair:
    return _load("shipped", "shipped")


@pytest.fixture(scope="session")
def synthetic() -> GoldenPair:
    return _load("synthetic", "synthetic")


@pytest.fixture(scope="session")
def synthetic_negative() -> GoldenPair:
    return _load("synthetic-negative", "synthetic")


@pytest.fixture(scope="session")
def all_pairs(shipped, synthetic, synthetic_negative) -> list[GoldenPair]:
    return [shipped, synthetic, synthetic_negative]
