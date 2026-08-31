"""Python port of src/NOTGEN.cbl (pipeline step 110, notice selection and generation).

Behaviour is characterized against GnuCOBOL runs of the legacy program; the COBOL
is the specification. Arithmetic uses Decimal with COBOL truncation semantics.

Record layouts come from copybooks/BMFMOD.cpy (150 bytes) and copybooks/NOTREC.cpy
(100 bytes). The DATECNV business-day shift (IRC 7503) is ported from the COBOL
shims src/DATECNV.cbl and src/DATCNV.cbl.
"""

from __future__ import annotations

import datetime
import sys
from decimal import Decimal
from typing import NamedTuple, Optional

MOD_RECORD_LEN = 150
NOTICE_RECORD_LEN = 100
REPORT_RECORD_LEN = 120

# BMF-MOD-REC field offsets (copybooks/BMFMOD.cpy)
OFF_EIN = (0, 9)
OFF_MFT = (9, 11)
OFF_TXPD = (11, 17)
OFF_NCTL = (17, 21)
OFF_NAME = (21, 56)
OFF_FSC = (56, 57)
OFF_SIC = (57, 58)
OFF_FRZ = (58, 66)
OFF_ASED = (66, 70)
OFF_RSED = (70, 74)
OFF_CSED = (74, 78)
OFF_ASSD = (78, 85)
OFF_DEP = (85, 92)
OFF_CRD = (92, 99)
OFF_PFTD = (99, 105)
OFF_PFTF = (105, 111)
OFF_PFTP = (111, 117)
OFF_INT = (117, 123)
OFF_W8 = (123, 131)
OFF_TCCNT = (131, 134)
OFF_FILL = (134, 150)

# DATECNV holiday table (MMDD), src/DATECNV.cbl HTAB
HOLIDAYS = ("0101", "0416", "0619", "0704", "1111", "1225")

# src/DATCNV.cbl DTAB
DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

NOTICE_DATE_GREG = 20260815  # hard-coded in 2200-BLD


def unpack_comp3(raw: bytes, scale: int) -> Decimal:
    """Decode a COMP-3 (packed decimal) field.

    The legacy runtime treats only sign nibble 0xD as negative; 0xB — negative
    under the IBM encoding — reads as positive. Verified by feeding NOTGEN one
    record per sign nibble 0x0-0xF (fixtures/sign_nibbles).
    """
    nibbles = "".join("%x%x" % (b >> 4, b & 0x0F) for b in raw)
    digits, sign = nibbles[:-1], nibbles[-1]
    value = Decimal(digits).scaleb(-scale)
    if sign == "d":
        value = -value
    return value


def pack_comp3(value: Decimal, digits: int, scale: int) -> bytes:
    """Encode a signed COMP-3 field of `digits` total digits."""
    scaled = int(value.scaleb(scale).to_integral_value(rounding="ROUND_DOWN"))
    negative = scaled < 0
    text = str(abs(scaled)).rjust(digits, "0")[-digits:]
    text += "d" if negative else "c"
    if len(text) % 2:
        text = "0" + text
    return bytes(int(text[i : i + 2], 16) for i in range(0, len(text), 2))


def truncate_field(value: Decimal, int_digits: int, scale: int) -> Decimal:
    """Emulate a MOVE/COMPUTE into PIC S9(int_digits)V9(scale): high-order
    truncation and low-order truncation, sign preserved."""
    scaled = int(value.scaleb(scale).to_integral_value(rounding="ROUND_DOWN"))
    limit = 10 ** (int_digits + scale)
    kept = abs(scaled) % limit
    if scaled < 0:
        kept = -kept
    return Decimal(kept).scaleb(-scale)


def edit_amount(value: Decimal) -> str:
    """PIC ZZZZZZZZ9.99- editing (13 characters)."""
    truncated = truncate_field(value, 9, 2)
    scaled = abs(int(truncated.scaleb(2)))
    cents = scaled % 100
    whole = scaled // 100
    body = "%9d.%02d" % (whole, cents)
    return body + ("-" if truncated < 0 else " ")


def _integer_of_date(greg: int) -> int:
    year, month, day = greg // 10000, (greg // 100) % 100, greg % 100
    return datetime.date(year, month, day).toordinal() - datetime.date(1600, 12, 31).toordinal()


def _date_of_integer(value: int) -> int:
    day = datetime.date.fromordinal(value + datetime.date(1600, 12, 31).toordinal())
    return day.year * 10000 + day.month * 100 + day.day


def _is_leap(year: int) -> int:
    """src/DATCNV.cbl 3000-LEAP."""
    if year % 4:
        return 0
    if year % 100:
        return 1
    return 1 if year % 400 == 0 else 0


def datcnv_to_julian(greg: int) -> tuple[Optional[int], str]:
    """src/DATCNV.cbl 1000-TOJUL. Returns (julian, return code)."""
    year, month, day = greg // 10000, (greg // 100) % 100, greg % 100
    if month < 1 or month > 12 or day < 1 or day > 31:
        return None, "8"
    leap = _is_leap(year)
    accum = 0
    for index in range(1, month):
        accum += DAYS_IN_MONTH[index - 1]
        if index == 2:
            accum += leap
    accum += day
    return year * 1000 + accum, "0"


def _day_of_week(greg: int) -> int:
    """src/DATECNV.cbl 4000-DOW: 1=Monday .. 7=Sunday."""
    dow = _integer_of_date(greg) % 7
    return 7 if dow == 0 else dow


def datecnv_business_day(greg: int) -> tuple[int, Optional[int], int]:
    """src/DATECNV.cbl 3000-BUS: shift forward off weekends and holidays.

    Returns (shifted gregorian, julian, day of week).
    """
    guard = 0
    shift = True
    while shift and guard <= 10:
        guard += 1
        shift = False
        if _day_of_week(greg) in (6, 7):
            shift = True
        month_day = "%04d" % (greg % 10000)
        for holiday in HOLIDAYS:
            if holiday == month_day:
                shift = True
        if shift:
            greg = _date_of_integer(_integer_of_date(greg) + 1)
    julian, _rc = datcnv_to_julian(greg)
    return greg, julian, _day_of_week(greg)


class ModuleRecord(NamedTuple):
    ein: str
    mft: str
    txpd: str
    nctl: str
    name: str
    frz: str
    assd: Decimal
    dep: Decimal
    crd: Decimal
    pftd: Decimal
    pftf: Decimal
    pftp: Decimal
    interest: Decimal

    @property
    def frz_a(self) -> str:
        return self.frz[0]

    @property
    def frz_r(self) -> str:
        return self.frz[3]

    @property
    def frz_z(self) -> str:
        return self.frz[6]


def parse_module_record(raw: bytes) -> ModuleRecord:
    def text(span):
        return raw[span[0] : span[1]].decode("latin-1")

    return ModuleRecord(
        ein=text(OFF_EIN),
        mft=text(OFF_MFT),
        txpd=text(OFF_TXPD),
        nctl=text(OFF_NCTL),
        name=text(OFF_NAME),
        frz=text(OFF_FRZ),
        assd=unpack_comp3(raw[OFF_ASSD[0] : OFF_ASSD[1]], 2),
        dep=unpack_comp3(raw[OFF_DEP[0] : OFF_DEP[1]], 2),
        crd=unpack_comp3(raw[OFF_CRD[0] : OFF_CRD[1]], 2),
        pftd=unpack_comp3(raw[OFF_PFTD[0] : OFF_PFTD[1]], 2),
        pftf=unpack_comp3(raw[OFF_PFTF[0] : OFF_PFTF[1]], 2),
        pftp=unpack_comp3(raw[OFF_PFTP[0] : OFF_PFTP[1]], 2),
        interest=unpack_comp3(raw[OFF_INT[0] : OFF_INT[1]], 2),
    )


CP_TEXT = {
    "0193": "DUPLICATE RETURN FILED",
    "0194": "POSSIBLE FTD PENALTY",
    "0215": "CIVIL PENALTY ASSESSED",
    "0161": "BALANCE DUE",
}
CP_TEXT_OTHER = "OVERPAYMENT - REFUND DUE"
SUPPRESSED_TEXT = "SUPPRESSED BY FREEZE"


class Selection(NamedTuple):
    cp: str
    severity: str
    suppressed: bool
    balance: Decimal
    liability: Decimal
    selected: bool


def select(record: ModuleRecord) -> Selection:
    """src/NOTGEN.cbl 2100-SEL selection logic."""
    liability = truncate_field(
        record.assd + record.pftd + record.pftf + record.pftp, 11, 2
    )
    balance = truncate_field(liability - record.dep - record.crd - record.interest, 11, 2)

    if record.frz_a == "A":
        cp, severity = "0193", "3"
    elif record.pftd > 0:
        cp, severity = "0194", "2"
    elif record.pftf > 0:
        cp, severity = "0215", "2"
    elif balance > 100:
        cp, severity = "0161", "1"
    elif balance < -100:
        cp, severity = "0267", "1"
    else:
        return Selection("    ", " ", False, balance, liability, False)

    suppressed = False
    if cp == "0267" and record.frz_r == "R":
        suppressed = True
    if record.frz_z == "Z":
        suppressed = True
    return Selection(cp, severity, suppressed, balance, liability, True)


def build_notice(record: ModuleRecord, sel: Selection, julian: int) -> bytes:
    """src/NOTGEN.cbl 2200-BLD, NOT-REC layout."""
    return (
        record.ein.encode("latin-1")
        + record.mft.encode("latin-1")
        + record.txpd.encode("latin-1")
        + sel.cp.encode("latin-1")
        + record.nctl.encode("latin-1")
        + record.name.encode("latin-1")
        + pack_comp3(sel.balance, 13, 2)
        + ("%07d" % julian).encode("latin-1")
        + sel.severity.encode("latin-1")
        + b" " * 25
    )


def build_report_line(record: ModuleRecord, sel: Selection, text: str) -> str:
    """NRPT record, 120 characters (line-sequential output trims trailing blanks)."""
    line = (
        "NOTGEN"
        + "  "
        + record.ein
        + " "
        + record.mft
        + " "
        + record.txpd
        + "  "
        + sel.cp
        + "  "
        + text.ljust(28)[:28]
        + "  "
        + edit_amount(sel.balance)
        + "  "
        + sel.severity
        + " " * 30
    )
    return line[:REPORT_RECORD_LEN]


class Counters(NamedTuple):
    read: int
    notices: int
    suppressed: int


def process(records: list[ModuleRecord]) -> tuple[list[bytes], list[str], Counters]:
    _greg, julian, _dow = datecnv_business_day(NOTICE_DATE_GREG)
    notices: list[bytes] = []
    report: list[str] = []
    read = suppressed = written = 0
    for record in records:
        read += 1
        sel = select(record)
        if not sel.selected:
            continue
        if sel.suppressed:
            suppressed += 1
            report.append(build_report_line(record, sel, SUPPRESSED_TEXT))
            continue
        notices.append(build_notice(record, sel, julian))
        written += 1
        report.append(
            build_report_line(record, sel, CP_TEXT.get(sel.cp, CP_TEXT_OTHER))
        )
    return notices, report, Counters(read, written, suppressed)


def read_module_file(path: str) -> list[ModuleRecord]:
    raw = open(path, "rb").read()
    return [
        parse_module_record(raw[i : i + MOD_RECORD_LEN])
        for i in range(0, len(raw), MOD_RECORD_LEN)
    ]


def run(modin_path: str, notice_path: str, report_path: str) -> Counters:
    notices, report, counters = process(read_module_file(modin_path))
    with open(notice_path, "wb") as handle:
        handle.write(b"".join(notices))
    with open(report_path, "w", encoding="latin-1", newline="\n") as handle:
        for line in report:
            handle.write(line.rstrip(" ") + "\n")
    return counters


def main(argv: list[str]) -> int:
    modin = argv[1] if len(argv) > 1 else "data/MODOFF.dat"
    notice = argv[2] if len(argv) > 2 else "data/NOTICE.dat"
    report = argv[3] if len(argv) > 3 else "data/NOTGEN.rpt"
    counters = run(modin, notice, report)
    print("NOTGEN  READ    %06d" % counters.read)
    print("NOTGEN  NOTICES %06d" % counters.notices)
    print("NOTGEN  SUPPRESS%06d" % counters.suppressed)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
