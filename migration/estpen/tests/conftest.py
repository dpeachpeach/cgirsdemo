import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))


def load_dat(name: str) -> bytes:
    return bytes.fromhex(FIXTURES.joinpath(name).read_text().strip())


def load_rpt(name: str) -> str:
    return FIXTURES.joinpath(name).read_text()


@pytest.fixture(scope="session")
def goldens():
    """The COBOL-captured golden pairs, keyed by name.

    Each value is (MODPEN.dat image, MODEST.dat image, ESTPEN.rpt text, counters).
    """
    return {
        "shipped": (
            load_dat("MODPEN-shipped.dat.hex"),
            load_dat("MODEST-shipped.dat.hex"),
            load_rpt("ESTPEN-shipped.rpt"),
            (52, 52, 1),
        ),
        "synthpipe": (
            load_dat("MODPEN-synthpipe.dat.hex"),
            load_dat("MODEST-synthpipe.dat.hex"),
            load_rpt("ESTPEN-synthpipe.rpt"),
            (62, 62, 7),
        ),
        "direct": (
            load_dat("MODPEN-direct.dat.hex"),
            load_dat("MODEST-direct.dat.hex"),
            load_rpt("ESTPEN-direct.rpt"),
            (7, 7, 5),
        ),
    }


@pytest.fixture(scope="session")
def case(goldens):
    """Look one EIN's golden triple out of a golden pair.

    Returns (input record, COBOL output record, COBOL report lines for that EIN).
    """
    def lookup(pair: str, ein: str):
        modin, modest, rpt, _ = goldens[pair]
        step = 150
        for offset in range(0, len(modin), step):
            if modin[offset:offset + 9].decode("ascii") == ein:
                lines = [ln for ln in rpt.splitlines() if ln[8:17] == ein]
                return modin[offset:offset + step], modest[offset:offset + step], lines
        raise AssertionError("EIN %s not present in golden pair %s" % (ein, pair))
    return lookup
