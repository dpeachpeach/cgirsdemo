"""Shared fixtures.

Every expected value used by this suite comes out of ``fixtures/``, which holds
input and output files captured from actual runs of the compiled COBOL
``FRZEVAL`` (GnuCOBOL 3.1.2). Nothing here is derived from the IRM, from the
program's comments, or from the rule as anyone understands it.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import frzeval  # noqa: E402

RECORD_LENGTH = frzeval.RECORD_LENGTH


@dataclass(frozen=True)
class GoldenPair:
    """One captured COBOL run: its input file and everything it produced."""

    name: str
    modin: bytes
    modot: bytes
    report_lines: list
    stdout: str

    def records_in(self) -> list:
        return [self.modin[i:i + RECORD_LENGTH] for i in range(0, len(self.modin), RECORD_LENGTH)]

    def records_out(self) -> list:
        return [self.modot[i:i + RECORD_LENGTH] for i in range(0, len(self.modot), RECORD_LENGTH)]

    def report_line_for(self, ein: str):
        matches = [line for line in self.report_lines if line[9:18] == ein]
        assert len(matches) <= 1, f"more than one report line for EIN {ein}"
        return matches[0] if matches else None


def _load(name: str) -> GoldenPair:
    base = ROOT / "fixtures" / name
    report = (base / "FRZEVAL.rpt").read_text().splitlines()
    return GoldenPair(
        name=name,
        modin=(base / "MODEST.dat").read_bytes(),
        modot=(base / "MODFRZ.dat").read_bytes(),
        report_lines=report,
        stdout=(base / "FRZEVAL.stdout").read_text(),
    )


@pytest.fixture(scope="session")
def shipped() -> GoldenPair:
    """Golden pair from the shipped data/ fixtures run through the pipeline."""
    return _load("shipped")


@pytest.fixture(scope="session")
def synthetic() -> GoldenPair:
    """Golden pair from the synthetic records built for uncovered behaviour."""
    return _load("synthetic")


@pytest.fixture(scope="session")
def synthetic_cases() -> dict:
    manifest = json.loads((ROOT / "fixtures" / "synthetic" / "cases.json").read_text())
    return {case["id"]: case for case in manifest["cases"]}


@pytest.fixture(scope="session")
def synthetic_run(synthetic):
    return frzeval.run(synthetic.modin)


@pytest.fixture(scope="session")
def shipped_run(shipped):
    return frzeval.run(shipped.modin)
