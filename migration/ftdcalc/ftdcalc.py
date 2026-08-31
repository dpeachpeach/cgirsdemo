#!/usr/bin/env python3
"""FTDCALC - failure to deposit penalty, step 040 of the BMF nightly cycle.

Python port of src/FTDCALC.cbl.  Ported against the COBOL shims src/DATCNV.cbl
and src/PENACC.cbl (the HLASM under src/asm/ does not execute).

This is a characterization port: behaviour observed in the legacy program is
reproduced exactly, defects included.  See the tests for the defects that are
pinned deliberately.
"""

import datetime
import sys
from decimal import Decimal

from cobol_types import (
    comp3_size,
    edited_amount,
    edited_zzz9_sign,
    pack_comp3,
    round_half_up,
    truncate,
    truncate_binary,
    unpack_comp3,
)

MOD_LRECL = 150
TRN_LRECL = 80
RPT_LRECL = 120

HIGH_VALUES = "\xff" * 17

DEFERRAL_FIRST = 202003
DEFERRAL_LAST = 202012
DEFERRAL_PCT = Decimal("0.5000")

MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


class ModuleRecord(object):
    """copybooks/BMFMOD.cpy - 150 byte packed master record."""

    LAYOUT = [
        ("ein", "X", 0, 9),
        ("mft", "X", 9, 2),
        ("txpd", "X", 11, 6),
        ("nctl", "X", 17, 4),
        ("name", "X", 21, 35),
        ("fsc", "X", 56, 1),
        ("sic", "X", 57, 1),
        ("frz", "X", 58, 8),
        ("ased", "3", 66, (7, 0, False)),
        ("rsed", "3", 70, (7, 0, False)),
        ("csed", "3", 74, (7, 0, False)),
        ("assd", "3", 78, (13, 2, True)),
        ("dep", "3", 85, (13, 2, True)),
        ("crd", "3", 92, (13, 2, True)),
        ("pftd", "3", 99, (11, 2, True)),
        ("pftf", "3", 105, (11, 2, True)),
        ("pftp", "3", 111, (11, 2, True)),
        ("int", "3", 117, (11, 2, True)),
        ("w8", "X", 123, 8),
        ("tccnt", "X", 131, 3),
        ("fill", "X", 134, 16),
    ]

    def __init__(self, raw):
        self.raw = bytearray(raw)
        for name, kind, offset, spec in self.LAYOUT:
            if kind == "X":
                setattr(self, name, self.raw[offset:offset + spec].decode("latin-1"))
            else:
                digits, scale, signed = spec
                size = comp3_size(digits)
                setattr(self, name, unpack_comp3(self.raw[offset:offset + size], scale))

    @property
    def key(self):
        return self.ein + self.mft + self.txpd

    @property
    def frz_a(self):
        return self.frz[0]

    @property
    def frz_s(self):
        return self.frz[4]

    def set_pftd(self, value):
        self.pftd = truncate(value, 11, 2)
        self.raw[99:105] = pack_comp3(self.pftd, 11, 2)

    def to_bytes(self):
        return bytes(self.raw)


class TranRecord(object):
    """copybooks/TRANREC.cpy - 80 byte packed transaction record."""

    def __init__(self, raw):
        self.raw = bytes(raw)
        text = self.raw.decode("latin-1")
        self.ein = text[0:9]
        self.mft = text[9:11]
        self.txpd = text[11:17]
        self.tc = text[17:20]
        self.dt = text[20:27]
        self.amt = unpack_comp3(self.raw[27:34], 2)
        self.cyc = text[34:40]
        self.dln = text[40:54]

    @property
    def key(self):
        return self.ein + self.mft + self.txpd


def datcnv(func, greg=0, jul=0):
    """src/DATCNV.cbl - julian / gregorian conversion shim.

    Returns (rc, greg, jul).  The day of month is never validated against the
    length of the month on the julian conversion, matching the shim.
    """
    if func == "J":
        year = int(str(greg).zfill(8)[0:4])
        month = int(str(greg).zfill(8)[4:6])
        day = int(str(greg).zfill(8)[6:8])
        if month < 1 or month > 12 or day < 1 or day > 31:
            return "8", greg, jul
        leap = _leap(year)
        accum = 0
        for index in range(1, month):
            accum += MONTH_DAYS[index - 1]
            if index == 2:
                accum += leap
        accum += day
        return "0", greg, year * 1000 + accum
    if func == "G":
        year = int(jul) // 1000
        accum = int(jul) - year * 1000
        leap = _leap(year)
        if accum < 1 or accum > 365 + leap:
            return "8", greg, jul
        month = 1
        while month <= 12:
            length = MONTH_DAYS[month - 1] + (leap if month == 2 else 0)
            if accum <= length:
                break
            accum -= length
            month += 1
        return "0", year * 10000 + month * 100 + accum, jul
    return "8", greg, jul


def _leap(year):
    if year % 4:
        return 0
    if year % 100:
        return 1
    return 1 if year % 400 == 0 else 0


def penacc(base, rate, accum):
    """src/PENACC.cbl - packed penalty accumulation shim.

    Returns (rc, amount, accum).  A negative base yields rc 8 and no
    accumulation.
    """
    if base < 0:
        return "8", Decimal("0.00"), accum
    product = truncate(base * rate, 17, 6)
    amount = truncate(round_half_up(product, 2), 11, 2)
    return "0", amount, truncate(accum + amount, 11, 2)


def integer_of_date(greg):
    """FUNCTION INTEGER-OF-DATE - days since 1600-12-31."""
    text = str(int(greg)).zfill(8)
    date = datetime.date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    return date.toordinal() - datetime.date(1600, 12, 31).toordinal()


def report_line(ein, mft, txpd, code, text, delinquency, tier, amount):
    line = (
        "FTDCALC" + "  " + ein + " " + mft + " " + txpd + "  "
        + code.ljust(4) + "  " + text.ljust(26)[:26] + "  "
        + edited_zzz9_sign(delinquency) + " " + str(int(tier) % 10) + " "
        + edited_amount(amount)
    )
    return line.ljust(RPT_LRECL).rstrip()


class Counters(object):
    def __init__(self):
        self.read = 0
        self.written = 0
        self.penalty = 0
        self.deminimis = 0
        self.bypass = 0

    def as_dict(self):
        return {
            "read": self.read,
            "written": self.written,
            "penalty": self.penalty,
            "deminimis": self.deminimis,
            "bypass": self.bypass,
        }


class _TranReader(object):
    def __init__(self, data):
        self.data = data
        self.position = 0
        self.eof = False
        self.key = ""
        self.record = None

    def read(self):
        if self.position + TRN_LRECL > len(self.data):
            self.eof = True
            self.key = HIGH_VALUES
            return
        self.record = TranRecord(self.data[self.position:self.position + TRN_LRECL])
        self.position += TRN_LRECL
        self.key = self.record.key


def run(modstat_path, tranin_path, modftd_path, rpt_path):
    with open(modstat_path, "rb") as handle:
        modules = handle.read()
    with open(tranin_path, "rb") as handle:
        trans = _TranReader(handle.read())

    counters = Counters()
    out_records = []
    report = []

    trans.read()
    offset = 0
    while offset + MOD_LRECL <= len(modules):
        module = ModuleRecord(modules[offset:offset + MOD_LRECL])
        offset += MOD_LRECL
        counters.read += 1
        _compute(module, trans, counters, report)
        out_records.append(module.to_bytes())
        counters.written += 1

    with open(modftd_path, "wb") as handle:
        handle.write(b"".join(out_records))
    with open(rpt_path, "w") as handle:
        for line in report:
            handle.write(line + "\n")
    return counters.as_dict()


def _compute(module, trans, counters, report):
    mkey = module.key
    penalty_accum = Decimal("0.00")
    max_delinquency = 0
    tier = 0
    rate = Decimal("0.0000")
    deposit_total = Decimal("0.00")
    bypass = False
    pic_flag = False
    pa_accum = Decimal("0.00")

    while not trans.eof and trans.key < mkey:
        trans.read()

    if module.frz_a == "A":
        bypass = True
    if module.frz_s == "S":
        bypass = True

    due_year = int(module.txpd[0:4])
    due_month = int(module.txpd[4:6]) + 1
    if due_month > 12:
        due_month -= 12
        due_year += 1
    due_day = 15
    if module.sic == "1":
        due_day = 3
    if module.sic == "2":
        due_day = 31
        due_month = 1
        due_year += 1
    due_greg = due_year * 10000 + due_month * 100 + due_day
    due_integer = integer_of_date(due_greg)
    datcnv("J", greg=due_greg)

    if module.w8[2:3] == "X":
        pic_flag = True

    while not trans.eof and trans.key == mkey:
        record = trans.record
        if int(record.tc) == 650:
            deposit_total = truncate(deposit_total + record.amt, 13, 2)
            rc, greg, _ = datcnv("G", jul=int(record.dt))
            if rc == "0":
                delinquency = truncate_binary(integer_of_date(greg) - due_integer, 5)
            else:
                delinquency = 0
            if delinquency > 0:
                if delinquency > max_delinquency:
                    max_delinquency = delinquency
                if delinquency < 6:
                    tier, rate = 1, Decimal("0.0200")
                elif delinquency < 16:
                    tier, rate = 2, Decimal("0.0500")
                else:
                    tier, rate = 3, Decimal("0.1000")
                if pic_flag and delinquency > 15:
                    tier, rate = 4, Decimal("0.1500")
                if not bypass and module.assd >= 1000:
                    _, amount, pa_accum = penacc(record.amt, rate, pa_accum)
                    penalty_accum = truncate(penalty_accum + amount, 11, 2)
                    report.append(report_line(
                        module.ein, module.mft, module.txpd,
                        "F401", "LATE DEPOSIT", delinquency, tier, amount))
        trans.read()

    if module.assd < 1000:
        counters.deminimis += 1
        report.append(report_line(
            module.ein, module.mft, module.txpd,
            "F402", "DE MINIMIS - NO PENALTY", 0, 0, Decimal("0.00")))
        penalty_accum = Decimal("0.00")

    txpd = int(module.txpd)
    if DEFERRAL_FIRST <= txpd <= DEFERRAL_LAST:
        deferral = truncate(module.assd * DEFERRAL_PCT, 13, 2)
        if deferral > 0:
            penalty_accum = truncate(penalty_accum - deferral, 11, 2)
            if penalty_accum < 0:
                penalty_accum = Decimal("0.00")
            report.append(report_line(
                module.ein, module.mft, module.txpd,
                "F404", "DEFERRED - SEC 2302", 0, 0, deferral))

    if bypass:
        counters.bypass += 1
        report.append(report_line(
            module.ein, module.mft, module.txpd,
            "F403", "FREEZE - PENALTY BYPASSED", 0, 0, Decimal("0.00")))
        penalty_accum = Decimal("0.00")

    if penalty_accum > 0:
        module.set_pftd(penalty_accum)
        counters.penalty += 1


def main(argv):
    paths = argv[1:]
    if not paths:
        paths = ["data/MODSTAT.dat", "data/TRANIN.dat",
                 "data/MODFTD.dat", "data/FTDCALC.rpt"]
    if len(paths) != 4:
        sys.stderr.write("usage: ftdcalc.py MODSTAT TRANIN MODFTD RPT\n")
        return 12
    counters = run(*paths)
    print("FTDCALC READ    %06d" % counters["read"])
    print("FTDCALC WRITTEN %06d" % counters["written"])
    print("FTDCALC PENALTY %06d" % counters["penalty"])
    print("FTDCALC DEMINIM %06d" % counters["deminimis"])
    print("FTDCALC BYPASS  %06d" % counters["bypass"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
