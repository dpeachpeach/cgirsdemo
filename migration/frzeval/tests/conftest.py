import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import frzeval  # noqa: E402

FIXTURES = ROOT / "fixtures"


class Golden:
    """A COBOL-captured input/output pair: MODEST.dat in, MODFRZ.dat + report out."""

    def __init__(self, name):
        self.name = name
        directory = FIXTURES / name
        self.records = frzeval.read_records(directory / "MODEST.dat")
        self.expected_records = frzeval.read_records(directory / "MODFRZ.dat")
        self.expected_report = (
            (directory / "FRZEVAL.rpt").read_text(encoding="latin-1").splitlines()
        )
        self.expected_console = (
            (directory / "console.txt").read_text(encoding="latin-1").splitlines()
        )

    def record_for(self, ein):
        for record in self.records:
            if record[0:9].decode() == ein:
                return record
        raise AssertionError(f"EIN {ein} not in {self.name} fixture")

    def expected_record_for(self, ein):
        for record in self.expected_records:
            if record[0:9].decode() == ein:
                return record
        raise AssertionError(f"EIN {ein} not in {self.name} golden output")

    def expected_report_for(self, ein):
        lines = [line for line in self.expected_report if line[9:18] == ein]
        return lines


@pytest.fixture(scope="session")
def shipped():
    return Golden("shipped")


@pytest.fixture(scope="session")
def synthetic():
    return Golden("synthetic")


def run_one(record):
    counters = frzeval.Counters()
    new_record, line = frzeval.evaluate_record(record, counters)
    return new_record, (line.render() if line else None), counters
