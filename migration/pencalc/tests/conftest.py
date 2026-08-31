import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))

import pencalc  # noqa: E402


class Golden:
    """A COBOL-captured golden pair plus the Python run over the same inputs."""

    def __init__(self, name: str):
        base = FIXTURES / name
        self.mod_in = (base / "MODFTD.dat").read_bytes()
        self.trn_in = (base / "TRANIN.dat").read_bytes()
        self.cobol_mod_out = (base / "MODPEN.dat").read_bytes()
        self.cobol_report = (base / "PENCALC.rpt").read_text()
        self.result = pencalc.run(self.mod_in, self.trn_in)

    def module(self, ein: str, txpd: str) -> pencalc.ModRecord:
        for i in range(0, len(self.result.mod_out), pencalc.MOD_LRECL):
            rec = pencalc.ModRecord(
                self.result.mod_out[i : i + pencalc.MOD_LRECL]
            )
            if rec.ein == ein and rec.txpd == txpd:
                return rec
        raise AssertionError(f"module {ein}/{txpd} not in output")

    def lines(self, ein: str) -> list[str]:
        return [ln for ln in self.cobol_report.splitlines() if ein in ln]


@pytest.fixture(scope="session")
def shipped() -> Golden:
    return Golden("shipped")


@pytest.fixture(scope="session")
def synthetic() -> Golden:
    return Golden("synthetic")
