"""Shared fixture plumbing for the STATCALC characterization suite."""

from __future__ import annotations

from pathlib import Path

from conftest import FIXTURES  # noqa: F401  (path bootstrap)

import statcalc as S


class Run:
    def __init__(self, name: str) -> None:
        self.dir = Path(FIXTURES) / name
        self.modin = (self.dir / "MODDUP.dat").read_bytes()
        self.job = S.Statcalc(S.Trace())
        self.modstat, self.report = self.job.run(self.modin)
        self.expected_modstat = (self.dir / "MODSTAT.dat").read_bytes()
        self.expected_report = (self.dir / "STATCALC.rpt").read_text()

    def out(self, index: int) -> S.Record:
        return S.Record(self.modstat[index * 150 : (index + 1) * 150])

    def inp(self, index: int) -> S.Record:
        return S.Record(self.modin[index * 150 : (index + 1) * 150])

    def by_ein(self, ein: str) -> S.Record:
        return self.out(self.index_of(ein))

    def index_of(self, ein: str) -> int:
        for i in range(len(self.modin) // 150):
            if self.inp(i).ein == ein:
                return i
        raise AssertionError(f"EIN {ein} not in {self.dir}")

    def report_lines(self) -> list[str]:
        return self.report.splitlines()

    def report_for(self, ein: str) -> list[str]:
        return [ln for ln in self.report_lines() if ln[10:19] == ein]


def ased(rec: S.Record) -> int:
    return int(rec.packed(S.F_ASED))


def rsed(rec: S.Record) -> int:
    return int(rec.packed(S.F_RSED))


def csed(rec: S.Record) -> int:
    return int(rec.packed(S.F_CSED))
