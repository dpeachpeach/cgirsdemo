import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dupchk  # noqa: E402


class Golden:
    """A golden pair captured from an actual run of the COBOL DUPCHK."""

    def __init__(self, name: str) -> None:
        self.dir = ROOT / "fixtures" / name
        self.modules_in = (self.dir / "BMFMOD.dat").read_bytes()
        self.transactions_in = (self.dir / "TRANIN.dat").read_bytes()
        self.modules_out = (self.dir / "MODDUP.dat").read_bytes()
        self.report = (self.dir / "DUPCHK.rpt").read_text(encoding="latin-1").splitlines()
        self.counters = (self.dir / "counters.txt").read_text().splitlines()
        self.result = dupchk.run(self.modules_in, self.transactions_in)

    def cobol_module(self, key: str) -> bytes:
        return self._find(self.modules_out, key)

    def python_module(self, key: str) -> bytes:
        return self._find(self.result.modules, key)

    @staticmethod
    def _find(data: bytes, key: str) -> bytes:
        wanted = key.encode("latin-1")
        for offset in range(0, len(data), dupchk.MOD_LEN):
            record = data[offset:offset + dupchk.MOD_LEN]
            if record[dupchk.BMF_KEY] == wanted:
                return record
        raise KeyError(key)

    def cobol_report_for(self, key: str) -> list[str]:
        return self._report_for(self.report, key)

    def python_report_for(self, key: str) -> list[str]:
        return self._report_for(self.result.report, key)

    @staticmethod
    def _report_for(lines: list[str], key: str) -> list[str]:
        ein, mft, txpd = key[:9], key[9:11], key[11:17]
        prefix = f"DUPCHK  {ein} {mft} {txpd}"
        return [line for line in lines if line.startswith(prefix)]


@pytest.fixture(scope="session")
def shipped() -> Golden:
    return Golden("shipped")


@pytest.fixture(scope="session")
def synthetic() -> Golden:
    return Golden("synthetic")
