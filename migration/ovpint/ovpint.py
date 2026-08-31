"""Python port of the COBOL program OVPINT (pipeline step 080).

Overpayment interest, IRC 6611.  Reads the 150-byte BMF tax module records
of data/MODFRZ.dat, writes data/MODINT.dat and the data/OVPINT.rpt report.

This is a characterization port: it reproduces what src/OVPINT.cbl actually
does, including its defects.  All arithmetic is decimal.
"""

from __future__ import annotations

import datetime
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

RECORD_LEN = 150
REPORT_LEN = 120

# 01 CYCDT PIC 9(8) VALUE 20260815 -- the hard-coded cycle date.
CYCDT = 20260815

# 01 WRT7 PIC S9(1)V9(4) COMP-3, MOVE 0.0700.
WRT7 = Decimal("0.0700")

# HTAB in src/DATECNV.cbl: "010104160619070411111225" redefined as 6 x 9(4).
HOLIDAYS = (101, 416, 619, 704, 1111, 1225)

_EPOCH = datetime.date(1600, 12, 31).toordinal()


# --------------------------------------------------------------------------
# COBOL data-type primitives
# --------------------------------------------------------------------------
def unpack_comp3(raw: bytes, scale: int) -> Decimal:
    """Decode a COMP-3 (packed decimal) field.  Sign nibble D/B = negative."""
    digits = []
    for byte in raw[:-1]:
        digits.append(byte >> 4)
        digits.append(byte & 0x0F)
    digits.append(raw[-1] >> 4)
    sign_nibble = raw[-1] & 0x0F
    value = Decimal("".join(str(d) for d in digits)).scaleb(-scale)
    if sign_nibble in (0x0B, 0x0D):
        value = -value
    return value


def pack_comp3(value: Decimal, digits: int, scale: int, signed: bool) -> bytes:
    """Encode a Decimal into a COMP-3 field of `digits` digits."""
    scaled = int(truncate(value, scale).scaleb(scale))
    negative = scaled < 0
    text = str(abs(scaled)).rjust(digits, "0")[-digits:]
    if signed:
        sign = 0x0D if negative else 0x0C
    else:
        sign = 0x0F
    nibbles = [int(c) for c in text] + [sign]
    if len(nibbles) % 2:
        nibbles.insert(0, 0)
    return bytes(
        (nibbles[i] << 4) | nibbles[i + 1] for i in range(0, len(nibbles), 2)
    )


def truncate(value: Decimal, scale: int) -> Decimal:
    """MOVE / COMPUTE without ROUNDED: truncate toward zero at `scale`."""
    quantum = Decimal(1).scaleb(-scale)
    return value.quantize(quantum, rounding="ROUND_DOWN")


def fit(value: Decimal, digits: int, scale: int) -> Decimal:
    """Store into PIC S9(digits-scale)V9(scale): truncate low order, drop
    high-order digits that do not fit."""
    value = truncate(value, scale)
    modulus = Decimal(1).scaleb(digits - scale)
    sign = -1 if value < 0 else 1
    return sign * (abs(value) % modulus)


def integer_of_date(yyyymmdd: int) -> int:
    """FUNCTION INTEGER-OF-DATE: days since 1600-12-31."""
    year, month, day = (
        yyyymmdd // 10000,
        (yyyymmdd // 100) % 100,
        yyyymmdd % 100,
    )
    return datetime.date(year, month, day).toordinal() - _EPOCH


def date_of_integer(number: int) -> int:
    """FUNCTION DATE-OF-INTEGER."""
    day = datetime.date.fromordinal(number + _EPOCH)
    return day.year * 10000 + day.month * 100 + day.day


def edit_z(value: Decimal, int_digits: int, dec_digits: int) -> str:
    """PIC ZZZ..9.99 style numeric edit: leading zero suppression, absolute
    value (the receiving items are unsigned), high-order digits dropped."""
    quantum = Decimal(1).scaleb(-dec_digits)
    scaled = abs(value).quantize(quantum, rounding="ROUND_DOWN")
    whole = int(scaled) % (10 ** int_digits)
    text = str(whole).rjust(int_digits)
    if dec_digits:
        frac = str(int((scaled - int(scaled)).scaleb(dec_digits)))
        return text + "." + frac.rjust(dec_digits, "0")
    return text


# --------------------------------------------------------------------------
# Record layout -- copybooks/BMFMOD.cpy
# --------------------------------------------------------------------------
@dataclass
class BmfMod:
    raw: bytes

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
    def assd(self) -> Decimal:
        return unpack_comp3(self.raw[78:85], 2)

    @property
    def dep(self) -> Decimal:
        return unpack_comp3(self.raw[85:92], 2)

    @property
    def crd(self) -> Decimal:
        return unpack_comp3(self.raw[92:99], 2)

    @property
    def pftd(self) -> Decimal:
        return unpack_comp3(self.raw[99:105], 2)

    @property
    def pftf(self) -> Decimal:
        return unpack_comp3(self.raw[105:111], 2)

    @property
    def pftp(self) -> Decimal:
        return unpack_comp3(self.raw[111:117], 2)

    @property
    def interest(self) -> Decimal:
        return unpack_comp3(self.raw[117:123], 2)

    def with_interest(self, value: Decimal) -> "BmfMod":
        packed = pack_comp3(value, 11, 2, signed=True)
        return BmfMod(self.raw[:117] + packed + self.raw[123:])


# --------------------------------------------------------------------------
# DATCNV / DATECNV shims (src/DATCNV.cbl, src/DATECNV.cbl)
# --------------------------------------------------------------------------
def day_of_week(gregorian: int) -> int:
    """DATECNV 4000-DOW.  MOD(INTEGER-OF-DATE, 7), zero mapped to 7."""
    dow = integer_of_date(gregorian) % 7
    return 7 if dow == 0 else dow


def datecnv_business_day(gregorian: int) -> int:
    """DATECNV function "B": IRC 7503 business-day shift.

    Advances one day at a time while the date falls on a Saturday/Sunday or
    matches the six-entry MMDD holiday table, giving up after 10 shifts
    (the WGUARD escape, which then returns a still-non-business day).
    """
    guard = 0
    shifted = True
    while shifted and guard <= 10:
        guard += 1
        shifted = False
        if day_of_week(gregorian) in (6, 7):
            shifted = True
        if gregorian % 10000 in HOLIDAYS:
            shifted = True
        if shifted:
            gregorian = date_of_integer(integer_of_date(gregorian) + 1)
    return gregorian


# --------------------------------------------------------------------------
# OVPINT
# --------------------------------------------------------------------------
@dataclass
class Result:
    record: BmfMod
    report_line: str | None
    interest_counted: bool
    forty_five_day: bool


def availability_date(txpd: str) -> int:
    """2100-INT: the 15th of the month after the tax period, shifted to the
    next business day."""
    xy = int(txpd[0:4])
    xm = int(txpd[4:6])
    xm += 1
    if xm > 12:
        xm -= 12
        xy += 1
    return datecnv_business_day(xy * 10000 + xm * 100 + 15)


def format_report(
    record: BmfMod, code: str, text: str, ovp: Decimal, days: int, interest: Decimal
) -> str:
    """Build the ORPT line.  OR-TXT is PIC X(26), so longer literals are
    truncated on the MOVE."""
    line = (
        "OVPINT"
        + "  "
        + record.ein
        + " "
        + record.mft
        + " "
        + record.txpd
        + "  "
        + code[:4].ljust(4)
        + "  "
        + text[:26].ljust(26)
        + "  "
        + edit_z(ovp, 9, 2)
        + " "
        + edit_z(Decimal(days), 4, 0)
        + " "
        + edit_z(interest, 7, 2)
    )
    return line.ljust(REPORT_LEN)


def process_record(record: BmfMod) -> Result:
    """2100-INT for one module record."""
    wlia = fit(record.assd + record.pftd + record.pftf + record.pftp, 13, 2)
    wovp = fit(record.dep + record.crd - wlia, 13, 2)
    if wovp <= 0:
        return Result(record, None, False, False)

    wavd = availability_date(record.txpd)
    wndy = integer_of_date(CYCDT) - integer_of_date(wavd)

    if wndy <= 45:
        line = format_report(
            record, "O801", "45 DAY RULE - NO INTEREST", wovp, wndy, Decimal(0)
        )
        return Result(record, line, False, True)

    wndy -= 30
    if wndy <= 0:  # unreachable: WNDY > 45 implies WNDY - 30 > 15
        return Result(record, None, False, False)

    wint = (wovp * WRT7 * wndy / Decimal(365)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    wint = fit(wint, 11, 2)
    line = format_report(
        record, "O802", "OVERPAYMENT INTEREST ALLOWED", wovp, wndy, wint
    )
    return Result(record.with_interest(wint), line, True, False)


def run(modin_path: str, modot_path: str, report_path: str) -> dict:
    """0000-MAIN."""
    counts = {"read": 0, "written": 0, "interest": 0, "forty_five": 0}
    with open(modin_path, "rb") as fin, open(modot_path, "wb") as fout, open(
        report_path, "w", newline="\n"
    ) as frpt:
        while True:
            raw = fin.read(RECORD_LEN)
            if len(raw) < RECORD_LEN:
                break
            counts["read"] += 1
            result = process_record(BmfMod(raw))
            if result.report_line is not None:
                frpt.write(result.report_line.rstrip(" ") + "\n")
            if result.interest_counted:
                counts["interest"] += 1
            if result.forty_five_day:
                counts["forty_five"] += 1
            fout.write(result.record.raw)
            counts["written"] += 1
    return counts


def main(argv: list[str]) -> int:
    modin = argv[1] if len(argv) > 1 else "data/MODFRZ.dat"
    modot = argv[2] if len(argv) > 2 else "data/MODINT.dat"
    report = argv[3] if len(argv) > 3 else "data/OVPINT.rpt"
    counts = run(modin, modot, report)
    print("OVPINT  READ    %06d" % counts["read"])
    print("OVPINT  WRITTEN %06d" % counts["written"])
    print("OVPINT  INTEREST%06d" % counts["interest"])
    print("OVPINT  45 DAY  %06d" % counts["forty_five"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
