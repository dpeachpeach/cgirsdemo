"""Loader for the captured COBOL golden pairs under migration/entval/fixtures/."""

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = PACKAGE_ROOT / "fixtures"

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import entval  # noqa: E402


def load_input(case: str) -> list[str]:
    return entval.split_records((FIXTURES / f"{case}.in.dat").read_bytes())


def expected_output(case: str) -> bytes:
    return (FIXTURES / f"{case}.out.dat").read_bytes()


def expected_report(case: str) -> str:
    return (FIXTURES / f"{case}.err.rpt").read_text()


def expected_console(case: str) -> list[str]:
    text = (FIXTURES / f"{case}.console.txt").read_text()
    return text.splitlines()


def run_case(case: str) -> entval.EntvalResult:
    return entval.run(load_input(case))


def output_record(result: entval.EntvalResult, ein: str) -> str:
    for record in result.records:
        if record[0:9] == ein:
            return record
    raise AssertionError(f"EIN {ein} not present in the output")


def golden_record(case: str, ein: str) -> str:
    data = expected_output(case).decode("ascii")
    for i in range(0, len(data), entval.RECORD_LENGTH):
        record = data[i:i + entval.RECORD_LENGTH]
        if record[0:9] == ein:
            return record
    raise AssertionError(f"EIN {ein} not present in the {case} golden output")
