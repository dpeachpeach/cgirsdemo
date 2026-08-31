"""Python port of the COBOL program NOTGEN (pipeline step 110).

Notice selection and generation.  Reads the settled module file
(data/MODOFF.dat), writes CP notice records (data/NOTICE.dat) and the
step report (data/NOTGEN.rpt).

The port is behaviour-for-behaviour with src/NOTGEN.cbl as compiled by
GnuCOBOL 3.1.2, including its defects.  DATECNV/DATCNV are ported from the
COBOL shims src/DATECNV.cbl and src/DATCNV.cbl; the HLASM under src/asm/
does not execute and is not the reference.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

MOD_LRECL = 150
NOT_LRECL = 100
RPT_LRECL = 120

# --- packed decimal (COMP-3) -------------------------------------------------


def unpack_comp3(raw: bytes, digits: int, scale: int) -> Decimal:
    nibbles = "".join(f"{b >> 4:x}{b & 0x0F:x}" for b in raw)
    nibbles = nibbles[-(digits + 1):]
    value = Decimal(nibbles[:-1]).scaleb(-scale)
    return -value if nibbles[-1] == "d" else value


def pack_comp3(value: Decimal, digits: int, scale: int) -> bytes:
    scaled = int(value.scaleb(scale).to_integral_value(rounding="ROUND_DOWN"))
    negative = scaled < 0
    text = f"{abs(scaled):0{digits}d}"[-digits:]
    sign = "d" if negative else "c"
    nibbles = text + sign
    if len(nibbles) % 2:
        nibbles = "0" + nibbles
    return bytes(
        int(nibbles[i], 16) << 4 | int(nibbles[i + 1], 16)
        for i in range(0, len(nibbles), 2)
    )


def truncate(value: Decimal, digits: int, scale: int) -> Decimal:
    """MOVE/COMPUTE into PIC S9(digits-scale)V9(scale) COMP-3."""
    scaled = int(value.scaleb(scale).to_integral_value(rounding="ROUND_DOWN"))
    negative = scaled < 0
    scaled = abs(scaled) % (10 ** digits)
    return Decimal(-scaled if negative else scaled).scaleb(-scale)


# --- DATCNV / DATECNV shims --------------------------------------------------

DTM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
HOL = ["0101", "0416", "0619", "0704", "1111", "1225"]
COBOL_DAY_ZERO = date(1600, 12, 31)


def _leap(year: int) -> int:
    kl = 0
    if year % 4 == 0:
        kl = 1
        if year % 100 == 0:
            kl = 0
            if year % 400 == 0:
                kl = 1
    return kl


def integer_of_date(greg: int) -> int:
    """FUNCTION INTEGER-OF-DATE: days since 1600-12-31, zero for a bad date."""
    text = f"{greg:08d}"
    try:
        day = date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return 0
    if day < date(1601, 1, 1):
        return 0
    return (day - COBOL_DAY_ZERO).days


@dataclass
class DvParm:
    """The parm block DATECNV and DATCNV share.

    DATECNV declares FUNC(1) GREG(8) JUL(7) DOW(1) RC(1) RSV(6) and passes
    DV-PARM(1:24) to DATCNV, which declares FUNC(1) GREG(8) JUL(7) RC(1)
    RSV(7).  The layouts disagree by one byte: DATCNV's return code lands on
    DATECNV's DOW byte, so ``dow`` doubles as DATCNV's RC here.
    """

    func: str = " "
    greg: int = 0
    jul: int = 0
    dow: int = 0
    rc: str = " "


def datcnv(parm: DvParm) -> None:
    """src/DATCNV.cbl.  Its return code is written into parm.dow."""
    parm.dow = 0
    if parm.func == "J":
        text = f"{parm.greg:08d}"
        ky, km, kd = int(text[0:4]), int(text[4:6]), int(text[6:8])
        if km < 1 or km > 12 or kd < 1 or kd > 31:
            parm.dow = 8
            return
        kl = _leap(ky)
        ka = 0
        for k1 in range(1, km):
            ka += DTM[k1 - 1]
            if k1 == 2:
                ka += kl
        ka += kd
        parm.jul = ky * 1000 + ka
    elif parm.func == "G":
        ky = parm.jul // 1000
        ka = parm.jul - ky * 1000
        kl = _leap(ky)
        if ka < 1 or ka > 365 + kl:
            parm.dow = 8
            return
        km = 1
        while km <= 12:
            kr = DTM[km - 1]
            if km == 2:
                kr += kl
            if ka <= kr:
                break
            ka -= kr
            km += 1
        parm.greg = ky * 10000 + km * 100 + ka
    else:
        parm.dow = 8


def _dow(parm: DvParm) -> None:
    """DATECNV 4000-DOW: 1=Monday .. 7=Sunday, and 7 for an unusable date."""
    wdow = integer_of_date(parm.greg) % 7
    parm.dow = 7 if wdow == 0 else wdow


def _advance_one_day(greg: int) -> int:
    text = f"{greg:08d}"
    moved = date(int(text[0:4]), int(text[4:6]), int(text[6:8])) + timedelta(days=1)
    return moved.year * 10000 + moved.month * 100 + moved.day


def datecnv(parm: DvParm) -> DvParm:
    """src/DATECNV.cbl."""
    parm.rc = "0"
    if parm.func == "J":
        datcnv(parm)
        # This test can never fire: DATCNV wrote its status into the DOW byte,
        # so parm.rc still holds the "0" moved in above.
        if parm.rc != "0":
            return parm
        _dow(parm)
    elif parm.func == "G":
        datcnv(parm)
        if parm.rc != "0":
            return parm
        _dow(parm)
    elif parm.func == "B":
        wguard = 0
        wsw = "Y"
        while wsw != "N" and wguard <= 10:
            wguard += 1
            wsw = "N"
            _dow(parm)
            if parm.dow in (6, 7):
                wsw = "Y"
            wmd = f"{parm.greg:08d}"[4:8]
            for holiday in HOL:
                if holiday == wmd:
                    wsw = "Y"
            if wsw == "Y":
                parm.greg = _advance_one_day(parm.greg)
        parm.func = "J"
        datcnv(parm)
        _dow(parm)
    else:
        parm.rc = "8"
    return parm


def datecnv_call(func: str, greg: int = 0, jul: int = 0) -> DvParm:
    return datecnv(DvParm(func=func, greg=greg, jul=jul))


# --- record layouts ---------------------------------------------------------


@dataclass
class ModuleRecord:
    ein: str
    mft: str
    txpd: str
    nctl: str
    name: str
    fsc: str
    sic: str
    frz: str
    assd: Decimal
    dep: Decimal
    crd: Decimal
    pftd: Decimal
    pftf: Decimal
    pftp: Decimal
    interest: Decimal

    @classmethod
    def parse(cls, raw: bytes) -> "ModuleRecord":
        text = raw.decode("latin-1")
        return cls(
            ein=text[0:9],
            mft=text[9:11],
            txpd=text[11:17],
            nctl=text[17:21],
            name=text[21:56],
            fsc=text[56],
            sic=text[57],
            frz=text[58:66],
            assd=unpack_comp3(raw[78:85], 13, 2),
            dep=unpack_comp3(raw[85:92], 13, 2),
            crd=unpack_comp3(raw[92:99], 13, 2),
            pftd=unpack_comp3(raw[99:105], 11, 2),
            pftf=unpack_comp3(raw[105:111], 11, 2),
            pftp=unpack_comp3(raw[111:117], 11, 2),
            interest=unpack_comp3(raw[117:123], 11, 2),
        )

    @property
    def frz_a(self) -> str:
        return self.frz[0]

    @property
    def frz_r(self) -> str:
        return self.frz[3]

    @property
    def frz_z(self) -> str:
        return self.frz[6]


CP_TEXT = {
    "0193": "DUPLICATE RETURN FILED",
    "0194": "POSSIBLE FTD PENALTY",
    "0215": "CIVIL PENALTY ASSESSED",
    "0161": "BALANCE DUE",
}
SUPPRESSED_TEXT = "SUPPRESSED BY FREEZE"
OTHER_TEXT = "OVERPAYMENT - REFUND DUE"

# NOTGEN moves the literal 20260815 into the DATECNV parm for every record,
# so the notice date is a constant rather than the cycle date.
NOTICE_DATE_GREG = 20260815


def format_amount_edited(value: Decimal) -> str:
    """PIC ZZZZZZZZ9.99- : nine integer digits, trailing sign."""
    scaled = int(value.scaleb(2).to_integral_value(rounding="ROUND_DOWN"))
    negative = scaled < 0
    scaled = abs(scaled)
    whole, cents = divmod(scaled, 100)
    whole %= 10 ** 9
    return f"{whole:9d}.{cents:02d}" + ("-" if negative else " ")


@dataclass
class Selection:
    cp: str
    severity: str
    suppressed: bool
    balance: Decimal
    liability: Decimal
    notice: Optional[bytes]
    report: Optional[str]


def select(rec: ModuleRecord) -> Selection:
    """2100-SEL / 2200-BLD for a single module record."""
    wlia = truncate(rec.assd + rec.pftd + rec.pftf + rec.pftp, 13, 2)
    wbal = truncate(wlia - rec.dep - rec.crd - rec.interest, 13, 2)

    if rec.frz_a == "A":
        wcpc, wsev = "0193", "3"
    elif rec.pftd > 0:
        wcpc, wsev = "0194", "2"
    elif rec.pftf > 0:
        wcpc, wsev = "0215", "2"
    elif wbal > 100:
        wcpc, wsev = "0161", "1"
    elif wbal < -100:
        wcpc, wsev = "0267", "1"
    else:
        return Selection("    ", " ", False, wbal, wlia, None, None)

    wsup = False
    if wcpc == "0267" and rec.frz_r == "R":
        wsup = True
    if rec.frz_z == "Z":
        wsup = True

    if wsup:
        return Selection(
            wcpc, wsev, True, wbal, wlia, None,
            build_report(rec, wcpc, wsev, wbal, SUPPRESSED_TEXT),
        )

    text = CP_TEXT.get(wcpc, OTHER_TEXT)
    return Selection(
        wcpc, wsev, False, wbal, wlia,
        build_notice(rec, wcpc, wsev, wbal),
        build_report(rec, wcpc, wsev, wbal, text),
    )


def build_notice(rec: ModuleRecord, wcpc: str, wsev: str, wbal: Decimal) -> bytes:
    jul = datecnv_call("B", greg=NOTICE_DATE_GREG).jul
    head = (rec.ein + rec.mft + rec.txpd + wcpc + rec.nctl + rec.name).encode("latin-1")
    tail = (f"{jul:07d}" + wsev + " " * 25).encode("latin-1")
    raw = head + pack_comp3(wbal, 13, 2) + tail
    assert len(raw) == NOT_LRECL, len(raw)
    return raw


def build_report(
    rec: ModuleRecord, wcpc: str, wsev: str, wbal: Decimal, text: str
) -> str:
    line = (
        "NOTGEN" + "  "
        + rec.ein + " " + rec.mft + " " + rec.txpd + "  "
        + wcpc + "  "
        + text.ljust(28)[:28] + "  "
        + format_amount_edited(wbal) + "  "
        + wsev
        + " " * 30
    )
    return line.ljust(RPT_LRECL)[:RPT_LRECL]


@dataclass
class Result:
    notices: bytes
    report: str
    read_count: int
    notice_count: int
    suppress_count: int

    @property
    def console(self) -> str:
        return (
            f"NOTGEN  READ    {self.read_count:06d}\n"
            f"NOTGEN  NOTICES {self.notice_count:06d}\n"
            f"NOTGEN  SUPPRESS{self.suppress_count:06d}\n"
        )


def run(module_file: bytes) -> Result:
    notices: List[bytes] = []
    lines: List[str] = []
    k1 = k2 = k3 = 0
    for offset in range(0, len(module_file) - MOD_LRECL + 1, MOD_LRECL):
        rec = ModuleRecord.parse(module_file[offset:offset + MOD_LRECL])
        k1 += 1
        sel = select(rec)
        if sel.report is None:
            continue
        if sel.suppressed:
            k3 += 1
        else:
            notices.append(sel.notice)
            k2 += 1
        lines.append(sel.report)
    report = "".join(line.rstrip(" ") + "\n" for line in lines)
    return Result(b"".join(notices), report, k1, k2, k3)


def main(argv: List[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("data")
    result = run((root / "MODOFF.dat").read_bytes())
    (root / "NOTICE.dat").write_bytes(result.notices)
    (root / "NOTGEN.rpt").write_text(result.report)
    sys.stdout.write(result.console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
