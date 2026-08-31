"""Python port of the COBOL program OVPINT (pipeline step 080).

Overpayment interest, IRC 6611.  Reads the module generation written by
FRZEVAL, writes the next generation plus a report line for every module that
either falls under the 45-day rule or is allowed interest.

This is a behaviour-preserving port of src/OVPINT.cbl and of the COBOL shims
it reaches through CALL "DATECNV" (src/DATECNV.cbl, which itself calls
src/DATCNV.cbl).  The HLASM under src/asm/ does not execute and is not the
reference.  Defects in the COBOL are reproduced here on purpose; see
migration/ovpint/tests/ for the characterization assertions.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

RECORD_LENGTH = 150

# 01 CYCDT PIC 9(8) VALUE 20260815.
CYCLE_DATE = 20260815

# 01 WRT7 PIC S9(1)V9(4) COMP-3, MOVE 0.0700.
INTEREST_RATE = Decimal("0.0700")

# HTAB in src/DATECNV.cbl: "010104160619070411111225" as six MMDD entries.
HOLIDAYS = (101, 416, 619, 704, 1111, 1225)

DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


# --------------------------------------------------------------------------
# COMP-3 (packed decimal)
# --------------------------------------------------------------------------
def store(value: Decimal, int_digits: int, scale: int) -> Decimal:
    """Store into a fixed-width numeric field: truncate to the field's scale,
    then drop the high-order digits that do not fit.  No ON SIZE ERROR is
    coded anywhere in OVPINT, so overflow is silent."""
    scaled = value.scaleb(scale).to_integral_value(rounding=ROUND_DOWN)
    kept = abs(int(scaled)) % (10 ** (int_digits + scale))
    result = Decimal(kept).scaleb(-scale)
    return -result if scaled < 0 else result


def packed_length(digits: int) -> int:
    return digits // 2 + 1


def unpack_decimal(raw: bytes, digits: int, scale: int, signed: bool) -> Decimal:
    """Decode a COMP-3 field.  Sign nibble D (and B) means negative."""
    nibbles = []
    for byte in raw:
        nibbles.append(byte >> 4)
        nibbles.append(byte & 0x0F)
    sign_nibble = nibbles.pop()
    text = "".join(str(n) for n in nibbles)[-digits:]
    value = Decimal(text).scaleb(-scale)
    if signed and sign_nibble in (0x0B, 0x0D):
        value = -value
    return value


def pack_decimal(value: Decimal, digits: int, scale: int, signed: bool) -> bytes:
    """Encode a COMP-3 field the way a COBOL MOVE into it would: the value is
    truncated to the field's scale and its low-order `digits` digits."""
    quantized = value.scaleb(scale).to_integral_value(rounding=ROUND_DOWN)
    negative = quantized < 0
    text = str(abs(int(quantized))).rjust(digits, "0")[-digits:]
    if signed:
        sign_nibble = 0x0D if negative else 0x0C
    else:
        sign_nibble = 0x0F
    nibbles = [int(c) for c in text.rjust(packed_length(digits) * 2 - 1, "0")]
    nibbles.append(sign_nibble)
    return bytes(
        (nibbles[i] << 4) | nibbles[i + 1] for i in range(0, len(nibbles), 2)
    )


# --------------------------------------------------------------------------
# BMFMOD record (copybooks/BMFMOD.cpy)
# --------------------------------------------------------------------------
@dataclass
class BmfMod:
    raw: bytes

    def _text(self, offset: int, length: int) -> str:
        return self.raw[offset : offset + length].decode("latin-1")

    def _packed(self, offset: int, digits: int, scale: int, signed: bool) -> Decimal:
        length = packed_length(digits)
        return unpack_decimal(
            self.raw[offset : offset + length], digits, scale, signed
        )

    @property
    def ein(self) -> str:
        return self._text(0, 9)

    @property
    def mft(self) -> str:
        return self._text(9, 2)

    @property
    def txpd(self) -> str:
        return self._text(11, 6)

    @property
    def assd(self) -> Decimal:
        return self._packed(78, 13, 2, True)

    @property
    def dep(self) -> Decimal:
        return self._packed(85, 13, 2, True)

    @property
    def crd(self) -> Decimal:
        return self._packed(92, 13, 2, True)

    @property
    def pftd(self) -> Decimal:
        return self._packed(99, 11, 2, True)

    @property
    def pftf(self) -> Decimal:
        return self._packed(105, 11, 2, True)

    @property
    def pftp(self) -> Decimal:
        return self._packed(111, 11, 2, True)

    @property
    def interest(self) -> Decimal:
        return self._packed(117, 11, 2, True)

    def with_interest(self, value: Decimal) -> "BmfMod":
        packed = pack_decimal(value, 11, 2, True)
        return BmfMod(self.raw[:117] + packed + self.raw[123:])


# --------------------------------------------------------------------------
# DATCNV / DATECNV shims
# --------------------------------------------------------------------------
def _is_leap(year: int) -> bool:
    """3000-LEAP in src/DATCNV.cbl."""
    if year % 4 != 0:
        return False
    if year % 100 != 0:
        return True
    return year % 400 == 0


def datcnv_to_julian(greg: int) -> tuple[int, str]:
    """1000-TOJUL in src/DATCNV.cbl.  Returns (julian, return-code)."""
    year, month, day = greg // 10000, (greg // 100) % 100, greg % 100
    if month < 1 or month > 12 or day < 1 or day > 31:
        return 0, "8"
    leap = 1 if _is_leap(year) else 0
    accumulated = 0
    for index in range(1, month):
        accumulated += DAYS_IN_MONTH[index - 1]
        if index == 2:
            accumulated += leap
    accumulated += day
    return year * 1000 + accumulated, "0"


def _integer_of_date(greg: int) -> int:
    """FUNCTION INTEGER-OF-DATE: days since 1600-12-31.  GnuCOBOL returns zero
    for an argument that is not a valid date, and OVPINT never checks."""
    year, month, day = greg // 10000, (greg // 100) % 100, greg % 100
    if year < 1601 or month < 1 or month > 12 or day < 1:
        return 0
    month_length = DAYS_IN_MONTH[month - 1] + (
        1 if month == 2 and _is_leap(year) else 0
    )
    if day > month_length:
        return 0
    total = 0
    for y in range(1601, year):
        total += 366 if _is_leap(y) else 365
    leap = 1 if _is_leap(year) else 0
    for m in range(1, month):
        total += DAYS_IN_MONTH[m - 1]
        if m == 2:
            total += leap
    return total + day


def _date_of_integer(value: int) -> int:
    """FUNCTION DATE-OF-INTEGER: inverse of _integer_of_date."""
    year = 1601
    remaining = value
    while True:
        length = 366 if _is_leap(year) else 365
        if remaining <= length:
            break
        remaining -= length
        year += 1
    leap = 1 if _is_leap(year) else 0
    month = 1
    while True:
        length = DAYS_IN_MONTH[month - 1] + (leap if month == 2 else 0)
        if remaining <= length:
            break
        remaining -= length
        month += 1
    return year * 10000 + month * 100 + remaining


def _day_of_week(greg: int) -> int:
    """4000-DOW in src/DATECNV.cbl: 1 = Monday .. 7 = Sunday."""
    dow = _integer_of_date(greg) % 7
    return 7 if dow == 0 else dow


def datecnv_business(greg: int) -> tuple[int, int, str]:
    """3000-BUS in src/DATECNV.cbl: shift forward off weekends and off the
    six fixed holidays in HTAB, at most ten iterations (WGUARD).  Returns
    (shifted gregorian, day of week, return-code)."""
    guard = 0
    switch = "Y"
    while switch != "N" and guard <= 10:
        guard += 1
        switch = "N"
        dow = _day_of_week(greg)
        if dow in (6, 7):
            switch = "Y"
        month_day = greg % 10000
        if month_day in HOLIDAYS:
            switch = "Y"
        if switch == "Y":
            greg = _date_of_integer(_integer_of_date(greg) + 1)
    _, return_code = datcnv_to_julian(greg)
    return greg, _day_of_week(greg), return_code


# --------------------------------------------------------------------------
# Report line (01 ORPT)
# --------------------------------------------------------------------------
def _edit_z(value: Decimal, int_digits: int, dec_digits: int) -> str:
    """PIC ZZZ..9.99 style numeric edit: leading zero suppression to spaces,
    the units position always printed, sign dropped, and the high-order digits
    of an oversized value truncated by the MOVE into the field."""
    scaled = abs(value).scaleb(dec_digits).to_integral_value(rounding=ROUND_DOWN)
    digits = str(int(scaled)).rjust(int_digits + dec_digits, "0")
    digits = digits[-(int_digits + dec_digits) :]
    whole, fraction = digits[:int_digits], digits[int_digits:]
    stripped = whole.lstrip("0")
    if stripped == "":
        stripped = "0"
    whole = stripped.rjust(int_digits)
    if dec_digits == 0:
        return whole
    return f"{whole}.{fraction}"


def report_line(
    ein: str,
    mft: str,
    txpd: str,
    code: str,
    text: str,
    overpayment: Decimal,
    days: int,
    interest: Decimal,
) -> str:
    """Build the 120-byte ORPT line.  OR-TXT is PIC X(26), so the 28-character
    literal "OVERPAYMENT INTEREST ALLOWED" is truncated on the MOVE."""
    line = (
        "OVPINT"
        + "  "
        + ein
        + " "
        + mft
        + " "
        + txpd
        + "  "
        + code[:4].ljust(4)
        + "  "
        + text[:26].ljust(26)
        + "  "
        + _edit_z(overpayment, 9, 2)
        + " "
        + _edit_z(Decimal(days), 4, 0)
        + " "
        + _edit_z(interest, 7, 2)
        + " " * 20
    )
    return line[:120]


# --------------------------------------------------------------------------
# 2100-INT
# --------------------------------------------------------------------------
@dataclass
class ModuleResult:
    record: BmfMod
    report: str | None = None
    interest_counted: bool = False
    forty_five_day_counted: bool = False


def process_module(module: BmfMod, cycle_date: int = CYCLE_DATE) -> ModuleResult:
    """2100-INT THRU 2100-X in src/OVPINT.cbl."""
    # WLIA and WOVP are PIC S9(11)V99.
    liability = store(
        module.assd + module.pftd + module.pftf + module.pftp, 11, 2
    )
    overpayment = store(module.dep + module.crd - liability, 11, 2)
    if overpayment <= 0:
        return ModuleResult(module)

    # XY is PIC 9(4) and XM is PIC 9(2), so ADD 1 TO XM wraps 99 to 00 and
    # the month-13 correction never fires for such a period.
    year = int(module.txpd[0:4])
    month = (int(module.txpd[4:6]) + 1) % 100
    if month > 12:
        month -= 12
        year = (year + 1) % 10000
    available = (year * 10000 + month * 100 + 15) % 100000000
    available, _dow, _rc = datecnv_business(available)

    days = _integer_of_date(cycle_date) - _integer_of_date(available)

    if days <= 45:
        return ModuleResult(
            module,
            report=report_line(
                module.ein,
                module.mft,
                module.txpd,
                "O801",
                "45 DAY RULE - NO INTEREST",
                overpayment,
                days,
                Decimal("0.00"),
            ),
            forty_five_day_counted=True,
        )

    days -= 30
    if days <= 0:
        # Unreachable: days > 45 above means days - 30 > 15.
        return ModuleResult(module)

    # COMPUTE WINT ROUNDED, WINT being PIC S9(9)V99: half-up on the target
    # scale, then the high-order digits that do not fit are dropped.
    interest = store(
        (overpayment * INTEREST_RATE * days / Decimal(365)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        9,
        2,
    )
    updated = module.with_interest(interest)
    return ModuleResult(
        updated,
        report=report_line(
            module.ein,
            module.mft,
            module.txpd,
            "O802",
            "OVERPAYMENT INTEREST ALLOWED",
            overpayment,
            days,
            interest,
        ),
        interest_counted=True,
    )


@dataclass
class RunResult:
    records: list[bytes]
    report: list[str]
    read: int
    written: int
    interest: int
    forty_five_day: int


def run(records: list[bytes], cycle_date: int = CYCLE_DATE) -> RunResult:
    """0000-MAIN / 2000-PROC in src/OVPINT.cbl."""
    out: list[bytes] = []
    report: list[str] = []
    interest = 0
    forty_five_day = 0
    for raw in records:
        result = process_module(BmfMod(raw), cycle_date)
        out.append(result.record.raw)
        if result.report is not None:
            report.append(result.report)
        interest += 1 if result.interest_counted else 0
        forty_five_day += 1 if result.forty_five_day_counted else 0
    return RunResult(out, report, len(records), len(out), interest, forty_five_day)


def read_records(path: str) -> list[bytes]:
    with open(path, "rb") as handle:
        data = handle.read()
    return [
        data[i : i + RECORD_LENGTH] for i in range(0, len(data), RECORD_LENGTH)
    ]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    base = argv[0] if argv else "."
    result = run(read_records(os.path.join(base, "data", "MODFRZ.dat")))
    with open(os.path.join(base, "data", "MODINT.dat"), "wb") as handle:
        handle.write(b"".join(result.records))
    with open(os.path.join(base, "data", "OVPINT.rpt"), "w") as handle:
        for line in result.report:
            # LINE SEQUENTIAL strips trailing spaces on WRITE.
            handle.write(line.rstrip() + "\n")
    print(f"OVPINT  READ    {result.read:06d}")
    print(f"OVPINT  WRITTEN {result.written:06d}")
    print(f"OVPINT  INTEREST{result.interest:06d}")
    print(f"OVPINT  45 DAY  {result.forty_five_day:06d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
