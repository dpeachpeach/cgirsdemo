import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))

import pencalc  # noqa: E402


def load_dataset(name):
    modules = pencalc.read_fixed(
        FIXTURES / name / "MODFTD.dat", pencalc.MOD_LRECL, pencalc.ModuleRecord
    )
    transactions = pencalc.read_fixed(
        FIXTURES / name / "TRANIN.dat", pencalc.TRN_LRECL, pencalc.TransactionRecord
    )
    engine = pencalc.Pencalc()
    records, report = engine.run(modules, transactions)
    return {
        "engine": engine,
        "records": records,
        "report": report,
        "cobol_modout": (FIXTURES / name / "MODPEN.dat").read_bytes(),
        "cobol_report": [
            line.rstrip("\n")
            for line in (FIXTURES / name / "PENCALC.rpt").read_text().splitlines()
        ],
    }


@pytest.fixture(scope="session")
def cases():
    return json.loads((FIXTURES / "cases.json").read_text())


@pytest.fixture(scope="session")
def shipped():
    return load_dataset("shipped")


@pytest.fixture(scope="session")
def synthetic():
    return load_dataset("synthetic")
