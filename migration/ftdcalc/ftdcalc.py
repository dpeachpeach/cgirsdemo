"""Python port of the COBOL program FTDCALC (step 040, IRC 6656 failure-to-deposit).

The COBOL in src/FTDCALC.cbl is the specification. Behaviour here mirrors it
statement for statement, including its defects; see the port report for the
list of reproduced defects and the proposed fixes that were NOT applied.

Called subprograms are ported from the COBOL shims src/DATCNV.cbl and
src/PENACC.cbl (the HLASM under src/asm/ does not execute).

All arithmetic is decimal.  Field widths, truncation points and ROUNDED
behaviour follow the PICTURE clauses of copybooks/BMFMOD.cpy,
copybooks/TRANREC.cpy and copybooks/PENWORK.cpy.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path

MOD_RECLEN = 150
TRN_RECLEN = 80

DTAB = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

RATE_TIER1 = Decimal("0.0200")
RATE_TIER2 = Decimal("0.0500")
RATE_TIER3 = Decimal("0.1000")
RATE_TIER4 = Decimal("0.1500")

WDF1 = 202003
WDF2 = 202012
WDPC = Decimal("0.5000")


# --------------------------------------------------------------------------
# COBOL data representation helpers
# --------------------------------------------------------------------------
def unpack_comp3(raw: bytes, scale: int) -> Decimal:
    """Unpack a COMP-3 (packed decimal) field."""
    digits = ""
    for byte in raw[:-1]:
        digits += str(byte >> 4) + str(byte & 0x0F)
    last = raw[-1]
    digits += str(last >> 4)
    sign = last & 0x0F
    value = Decimal(digits or "0")
    if scale:
        value = value.scaleb(-scale)
    if sign == 0x0D:
        value = -value
    return value


def pack_comp3(value: Decimal, digits: int, scale: int, signed: bool = True) -> bytes:
    """Pack a Decimal into COMP-3, truncating high-order digits like COBOL MOVE."""
    quantized = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_DOWN)
    negative = quantized < 0
    unscaled = abs(quantized).scaleb(scale).to_integral_value(rounding=ROUND_DOWN)
    text = str(int(unscaled)).zfill(digits)[-digits:]
    if signed:
        sign_nibble = "D" if negative else "C"
    else:
        sign_nibble = "F"
    nibbles = text + sign_nibble
    if len(nibbles) % 2:
        nibbles = "0" + nibbles
    return bytes.fromhex(nibbles)


def truncate(value: Decimal, digits: int, scale: int) -> Decimal:
    """Store into PIC S9(digits-scale)V9(scale): truncate low order, wrap high order."""
    quantized = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_DOWN)
    negative = quantized < 0
    unscaled = abs(quantized).scaleb(scale).to_integral_value(rounding=ROUND_DOWN)
    unscaled = unscaled % (10 ** digits)
    result = Decimal(unscaled).scaleb(-scale)
    return -result if negative else result


def edit_amount(value: Decimal) -> str:
    """PIC ZZZZZZZ9.99 - eight integer positions, high-order truncation, zero suppression."""
    quantized = abs(value).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    cents = int(quantized.scaleb(2).to_integral_value(rounding=ROUND_DOWN)) % (10 ** 10)
    text = str(cents).zfill(10)
    body = text[:8].lstrip("0")
    body = body.rjust(8) if body else "       0"
    if len(body) == 8 and body.strip() == "":
        body = "       0"
    return f"{body}.{text[8:]}"


def edit_delinquency(value: int) -> str:
    """PIC ZZZ9- - four digits, high-order truncation, trailing sign."""
    magnitude = abs(int(value)) % 10000
    text = str(magnitude).zfill(4)
    body = text[:3].lstrip("0").rjust(3) + text[3]
    sign = "-" if value < 0 else " "
    return body + sign


def binary_truncate(value: int, digits: int) -> int:
    """COMPUTE into PIC S9(n) COMP - GnuCOBOL default truncates to n decimal digits."""
    negative = value < 0
    result = abs(value) % (10 ** digits)
    return -result if negative else result


def integer_of_date(yyyymmdd: int) -> int:
    """FUNCTION INTEGER-OF-DATE - days since 1600-12-31."""
    year, month, day = yyyymmdd // 10000, (yyyymmdd // 100) % 100, yyyymmdd % 100
    total = 0
    for y in range(1601, year):
        total += 366 if is_leap(y) else 365
    for m in range(1, month):
        total += DTAB[m - 1] + (1 if m == 2 and is_leap(year) else 0)
    return total + day


def is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


# --------------------------------------------------------------------------
# Ported subprograms
# --------------------------------------------------------------------------
@dataclass
class DcParm:
    """DC-PARM, the 24-byte DATCNV parameter block."""

    func: str = " "
    greg: int = 0
    jul: int = 0
    rc: str = "0"


def _no_trace(_branch: str) -> None:
    pass


def datcnv(parm: DcParm, hit=_no_trace) -> None:
    """Port of the COBOL shim src/DATCNV.cbl."""
    parm.rc = "0"
    if parm.func == "J":
        hit("DATCNV-01")
        _to_julian(parm, hit)
    elif parm.func == "G":
        hit("DATCNV-02")
        _to_gregorian(parm, hit)
    else:
        hit("DATCNV-03")
        parm.rc = "8"


def _to_julian(parm: DcParm, hit) -> None:
    text = str(parm.greg).zfill(8)
    ky, km, kd = int(text[0:4]), int(text[4:6]), int(text[6:8])
    if km < 1 or km > 12 or kd < 1 or kd > 31:
        hit("DATCNV-04")
        parm.rc = "8"
        return
    hit("DATCNV-05")
    kl = 1 if is_leap(ky) else 0
    ka = 0
    k1 = 1
    while k1 < km:
        ka += DTAB[k1 - 1]
        if k1 == 2:
            hit("DATCNV-06")
            ka += kl
        k1 += 1
    ka += kd
    parm.jul = (ky * 1000 + ka) % 10 ** 7


def _to_gregorian(parm: DcParm, hit) -> None:
    ky = parm.jul // 1000
    ka = parm.jul - ky * 1000
    kl = 1 if is_leap(ky) else 0
    if ka < 1 or ka > 365 + kl:
        hit("DATCNV-07")
        parm.rc = "8"
        return
    hit("DATCNV-08")
    km = 1
    while km <= 12:
        kr = DTAB[km - 1]
        if km == 2:
            hit("DATCNV-09")
            kr += kl
        if ka <= kr:
            hit("DATCNV-10")
            break
        ka -= kr
        km += 1
    else:
        hit("DATCNV-11")
        km = 13
    parm.greg = (ky * 10000 + km * 100 + ka) % 10 ** 8


@dataclass
class PaParm:
    """PA-PARM, the 32-byte PENACC parameter block."""

    bas: Decimal = Decimal(0)
    rt: Decimal = Decimal(0)
    acc: Decimal = Decimal(0)
    amt: Decimal = Decimal(0)
    rc: str = "0"


def penacc(parm: PaParm, hit=_no_trace) -> None:
    """Port of the COBOL shim src/PENACC.cbl."""
    parm.rc = "0"
    if parm.bas < 0:
        hit("PENACC-01")
        parm.rc = "8"
        parm.amt = Decimal(0)
        return
    hit("PENACC-02")
    pz = truncate(parm.bas * parm.rt, 17, 6)
    parm.amt = truncate(pz.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), 11, 2)
    parm.acc = truncate(parm.acc + parm.amt, 11, 2)


# --------------------------------------------------------------------------
# Record layouts
# --------------------------------------------------------------------------
@dataclass
class ModRecord:
    """BMF-MOD-REC as laid out by copybooks/BMFMOD.cpy."""

    raw: bytes

    @property
    def key(self) -> str:
        return self.raw[0:17].decode("latin-1")

    @property
    def ein(self) -> str:
        return self.raw[0:9].decode("latin-1")

    @property
    def mft(self) -> str:
        return self.raw[9:11].decode("latin-1")

    @property
    def txpd(self) -> str:
        return self.raw[11:17].decode("latin-1")

    @property
    def sic(self) -> str:
        return self.raw[57:58].decode("latin-1")

    @property
    def frz_a(self) -> str:
        return self.raw[58:59].decode("latin-1")

    @property
    def frz_s(self) -> str:
        return self.raw[62:63].decode("latin-1")

    @property
    def assd(self) -> Decimal:
        return unpack_comp3(self.raw[78:85], 2)

    @property
    def w8(self) -> str:
        return self.raw[123:131].decode("latin-1")

    def with_pftd(self, value: Decimal) -> "ModRecord":
        packed = pack_comp3(value, 11, 2)
        return ModRecord(self.raw[:99] + packed + self.raw[105:])


@dataclass
class TrnRecord:
    """TRN-REC as laid out by copybooks/TRANREC.cpy."""

    raw: bytes

    @property
    def key(self) -> str:
        return self.raw[0:17].decode("latin-1")

    @property
    def tc(self) -> int:
        return int(self.raw[17:20])

    @property
    def dt(self) -> int:
        return int(self.raw[20:27])

    @property
    def amt(self) -> Decimal:
        return unpack_comp3(self.raw[27:34], 2)


HIGH_VALUES = "\xff" * 17


# --------------------------------------------------------------------------
# FTDCALC
# --------------------------------------------------------------------------
@dataclass
class Result:
    """What one FTDCALC run produced."""

    modout: bytes
    report: list[str]
    counters: dict[str, int]
    branches: set[str]


def run(modin: bytes, trnin: bytes, trace: set[str] | None = None) -> Result:
    """Port of src/FTDCALC.cbl 0000-MAIN."""
    branches: set[str] = trace if trace is not None else set()
    hit = branches.add

    mod_records = [
        ModRecord(modin[i : i + MOD_RECLEN]) for i in range(0, len(modin), MOD_RECLEN)
    ]
    trn_records = [
        TrnRecord(trnin[i : i + TRN_RECLEN]) for i in range(0, len(trnin), TRN_RECLEN)
    ]

    state = _TrnCursor(trn_records, hit)
    counters = {"read": 0, "written": 0, "penalty": 0, "deminimis": 0, "bypass": 0}
    out = bytearray()
    report: list[str] = []

    state.read_next()
    for record in mod_records:
        hit("FTD-02")
        counters["read"] += 1
        updated = _compute(record, state, counters, report, hit)
        out += updated.raw
        counters["written"] += 1
    hit("FTD-01")

    return Result(bytes(out), report, counters, branches)


class _TrnCursor:
    """The TRNIN file plus TKEY, driven by 8100-RDTRN."""

    def __init__(self, records: list[TrnRecord], hit) -> None:
        self._records = records
        self._index = 0
        self._hit = hit
        self.eof = False
        self.key = ""
        self.current: TrnRecord | None = None

    def read_next(self) -> None:
        if self._index >= len(self._records):
            self._hit("FTD-46")
            self.eof = True
            self.key = HIGH_VALUES
            self.current = None
            return
        self._hit("FTD-47")
        self.current = self._records[self._index]
        self._index += 1
        self.key = self.current.key


def _compute(
    record: ModRecord,
    trn: _TrnCursor,
    counters: dict[str, int],
    report: list[str],
    hit,
) -> ModRecord:
    """Port of 3000-COMP."""
    mkey = record.key
    pw_acc = Decimal(0)
    pw_dlq = 0
    pw_tier = 0
    pw_rt = Decimal(0)
    wndp = 0
    wtot = Decimal(0)
    wbyp = "N"
    wpic = "N"
    pa = PaParm()

    skipped = False
    while not trn.eof and trn.key < mkey:
        hit("FTD-03")
        skipped = True
        trn.read_next()
    if not skipped:
        hit("FTD-04")

    if record.frz_a == "A":
        hit("FTD-05")
        wbyp = "Y"
    else:
        hit("FTD-06")
    if record.frz_s == "S":
        hit("FTD-07")
        wbyp = "Y"
    else:
        hit("FTD-08")

    uy = int(record.txpd[0:4])
    um = int(record.txpd[4:6]) + 1
    if um > 12:
        hit("FTD-09")
        um -= 12
        uy += 1
    else:
        hit("FTD-10")
    udy = 15
    if record.sic == "1":
        hit("FTD-11")
        udy = 3
    else:
        hit("FTD-12")
    if record.sic == "2":
        hit("FTD-13")
        udy = 31
        um = 1
        uy = (uy + 1) % 10000
    else:
        hit("FTD-14")

    gu = (uy * 10000 + um * 100 + udy) % 10 ** 8
    iu = integer_of_date(gu)
    dcp = DcParm(func="J", greg=gu)
    datcnv(dcp, hit)

    if record.w8[2:3] == "X":
        hit("FTD-15")
        wpic = "Y"
    else:
        hit("FTD-16")

    matched = False
    while not trn.eof and trn.key == mkey:
        hit("FTD-17")
        matched = True
        current = trn.current
        assert current is not None
        if current.tc == 650:
            hit("FTD-19")
            wndp += 1
            wtot = truncate(wtot + current.amt, 13, 2)
            dcp = DcParm(func="G", jul=current.dt, greg=0)
            datcnv(dcp, hit)
            if dcp.rc == "0":
                hit("FTD-21")
                gd = dcp.greg
                idd = integer_of_date(gd)
                dl = binary_truncate(idd - iu, 5)
            else:
                hit("FTD-22")
                dl = 0
            if dl > 0:
                hit("FTD-23")
                if dl > pw_dlq:
                    hit("FTD-25")
                    pw_dlq = dl
                else:
                    hit("FTD-26")
                if dl < 6:
                    hit("FTD-27")
                    pw_tier, pw_rt = 1, RATE_TIER1
                elif dl < 16:
                    hit("FTD-28")
                    pw_tier, pw_rt = 2, RATE_TIER2
                else:
                    hit("FTD-29")
                    pw_tier, pw_rt = 3, RATE_TIER3
                if wpic == "Y" and dl > 15:
                    hit("FTD-30")
                    pw_tier, pw_rt = 4, RATE_TIER4
                else:
                    hit("FTD-31")
                if wbyp == "N" and record.assd >= 1000:
                    hit("FTD-32")
                    pa.bas = current.amt
                    pa.rt = pw_rt
                    penacc(pa, hit)
                    pw_acc = truncate(pw_acc + pa.amt, 11, 2)
                    report.append(
                        _report_line(record, "F401", "LATE DEPOSIT", dl, pw_tier, pa.amt)
                    )
                else:
                    hit("FTD-33")
            else:
                hit("FTD-24")
        else:
            hit("FTD-20")
        trn.read_next()
    if not matched:
        hit("FTD-18")

    if record.assd < 1000:
        hit("FTD-34")
        counters["deminimis"] += 1
        report.append(
            _report_line(record, "F402", "DE MINIMIS - NO PENALTY", 0, 0, Decimal(0))
        )
        pw_acc = Decimal(0)
    else:
        hit("FTD-35")

    txpd = int(record.txpd)
    if WDF1 <= txpd <= WDF2:
        hit("FTD-36")
        wdfr = truncate(record.assd * WDPC, 13, 2)
        if wdfr > 0:
            hit("FTD-38")
            pw_acc = truncate(pw_acc - wdfr, 11, 2)
            if pw_acc < 0:
                hit("FTD-40")
                pw_acc = Decimal(0)
            else:
                hit("FTD-41")
            report.append(
                _report_line(record, "F404", "DEFERRED - SEC 2302", 0, 0, wdfr)
            )
        else:
            hit("FTD-39")
    else:
        hit("FTD-37")

    if wbyp == "Y":
        hit("FTD-42")
        counters["bypass"] += 1
        report.append(
            _report_line(record, "F403", "FREEZE - PENALTY BYPASSED", 0, 0, Decimal(0))
        )
        pw_acc = Decimal(0)
    else:
        hit("FTD-43")

    if pw_acc > 0:
        hit("FTD-44")
        counters["penalty"] += 1
        return record.with_pftd(pw_acc)
    hit("FTD-45")
    return record


def _report_line(
    record: ModRecord, code: str, text: str, dl: int, tier: int, amount: Decimal
) -> str:
    """Build one FRPT line; LINE SEQUENTIAL strips the trailing spaces."""
    line = (
        "FTDCALC"
        + "  "
        + record.ein
        + " "
        + record.mft
        + " "
        + record.txpd
        + "  "
        + f"{code:<4}"
        + "  "
        + f"{text:<26}"
        + "  "
        + edit_delinquency(dl)
        + " "
        + str(tier)
        + " "
        + edit_amount(amount)
        + " " * 30
    )
    return line.ljust(120).rstrip()


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(".")
    result = run(
        (root / "data/MODSTAT.dat").read_bytes(), (root / "data/TRANIN.dat").read_bytes()
    )
    (root / "data/MODFTD.dat").write_bytes(result.modout)
    (root / "data/FTDCALC.rpt").write_text(
        "".join(line + "\n" for line in result.report)
    )
    print(f"FTDCALC READ    {result.counters['read']:06d}")
    print(f"FTDCALC WRITTEN {result.counters['written']:06d}")
    print(f"FTDCALC PENALTY {result.counters['penalty']:06d}")
    print(f"FTDCALC DEMINIM {result.counters['deminimis']:06d}")
    print(f"FTDCALC BYPASS  {result.counters['bypass']:06d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
