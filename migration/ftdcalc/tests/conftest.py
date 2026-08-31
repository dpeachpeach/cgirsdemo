import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(ROOT, "fixtures")

sys.path.insert(0, ROOT)

import ftdcalc  # noqa: E402


class Golden(object):
    """One COBOL-captured input/output pair plus the port's output for it."""

    def __init__(self, name, tmpdir):
        directory = os.path.join(FIXTURES, name)
        self.name = name
        self.modstat = os.path.join(directory, "MODSTAT.dat")
        self.tranin = os.path.join(directory, "TRANIN.dat")
        with open(os.path.join(directory, "MODFTD.dat"), "rb") as handle:
            self.cobol_modules = handle.read()
        with open(os.path.join(directory, "FTDCALC.rpt")) as handle:
            self.cobol_report = handle.read().splitlines()
        with open(os.path.join(directory, "counters.json")) as handle:
            self.cobol_counters = json.load(handle)

        self.python_modules_path = os.path.join(str(tmpdir), "MODFTD.dat")
        self.python_report_path = os.path.join(str(tmpdir), "FTDCALC.rpt")
        self.python_counters = ftdcalc.run(
            self.modstat, self.tranin,
            self.python_modules_path, self.python_report_path)
        with open(self.python_modules_path, "rb") as handle:
            self.python_modules = handle.read()
        with open(self.python_report_path) as handle:
            self.python_report = handle.read().splitlines()

    def cobol_lines(self, ein, code=None):
        return [line for line in self.cobol_report
                if line[9:18] == ein and (code is None or line[30:34] == code)]

    def python_lines(self, ein, code=None):
        return [line for line in self.python_report
                if line[9:18] == ein and (code is None or line[30:34] == code)]

    def module(self, source, ein):
        records = source if isinstance(source, bytes) else source
        for offset in range(0, len(records), ftdcalc.MOD_LRECL):
            record = ftdcalc.ModuleRecord(records[offset:offset + ftdcalc.MOD_LRECL])
            if record.ein == ein:
                return record
        raise AssertionError("module %s not in output" % ein)

    def cobol_module(self, ein):
        return self.module(self.cobol_modules, ein)

    def python_module(self, ein):
        return self.module(self.python_modules, ein)


@pytest.fixture(scope="session")
def shipped(tmpdir_factory):
    return Golden("shipped", tmpdir_factory.mktemp("shipped"))


@pytest.fixture(scope="session")
def synthetic(tmpdir_factory):
    return Golden("synthetic", tmpdir_factory.mktemp("synthetic"))
