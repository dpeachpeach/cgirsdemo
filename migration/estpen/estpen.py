"""Python port of the COBOL program ESTPEN (pipeline step 060).

Corporate estimated tax penalty, IRC 6655.  Reads the module record
generation written by PENCALC, writes the next generation plus the
ESTPEN report.  Behaviour is characterized against src/ESTPEN.cbl as
compiled by GnuCOBOL; defects of the legacy program are reproduced, not
corrected.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, getcontext
from pathlib import Path

getcontext().prec = 60

RECORD_LEN = 150

# BMFMOD.cpy field displacements (0-relative, byte offsets in the packed record)
OFF_EIN = (0, 9)
OFF_MFT = (9, 11)
OFF_TXPD = (11, 17)
OFF_ASSD = (78, 85)     # S9(11)V99 COMP-3, 7 bytes
OFF_DEP = (85, 92)      # S9(11)V99 COMP-3, 7 bytes
OFF_PFTP = (111, 117)   # S9(9)V99 COMP-3, 6 bytes

QUARTER_DAYS = {1: 275, 2: 183, 3: 92, 4: 30}
WQRT = Decimal("0.0008")

CENT = Decimal("0.01")


def unpack_comp3(raw: bytes, scale: int) -> Decimal:
    """Decode a COMP-3 (packed decimal) field."""
    digits = raw.hex()
    sign_nibble = digits[-1]
    value = Decimal(digits[:-1] or "0").scaleb(-scale)
    if sign_nibble in ("b", "d"):
        value = -value
    return value


def pack_comp3(value: Decimal, digits: int, scale: int) -> bytes:
    """Encode a signed COMP-3 field of `digits` total digits."""
    scaled = int(value.scaleb(scale).to_integral_value(rounding=ROUND_DOWN))
    negative = scaled < 0
    scaled = abs(scaled) % (10 ** digits)
    text = str(scaled).zfill(digits) + ("d" if negative else "c")
    if len(text) % 2:
        text = "0" + text
    return bytes.fromhex(text)


def truncate(value: Decimal, int_digits: int, scale: int = 2) -> Decimal:
    """MOVE/COMPUTE into a PIC S9(int_digits)V99 field: no ROUNDED clause
    means the low-order digits are truncated and the high-order digits
    beyond the picture are dropped."""
    truncated = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_DOWN)
    limit = Decimal(10) ** int_digits
    sign = -1 if truncated < 0 else 1
    return sign * (abs(truncated) % limit)


def rounded(value: Decimal, int_digits: int, scale: int = 2) -> Decimal:
    """COMPUTE ... ROUNDED into PIC S9(int_digits)V99: half-up on the
    target scale, then the same high-order truncation."""
    half_up = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
    limit = Decimal(10) ** int_digits
    sign = -1 if half_up < 0 else 1
    return sign * (abs(half_up) % limit)


def edit_z(value: Decimal, int_digits: int) -> str:
    """Format into a PIC Z...Z9.99 edited field: unsigned, high-order
    digits past the picture are lost, leading zeros become spaces."""
    absolute = abs(value).quantize(CENT, rounding=ROUND_DOWN)
    absolute = absolute % (Decimal(10) ** int_digits)
    whole = int(absolute)
    cents = int((absolute - whole).scaleb(2))
    return f"{whole:>{int_digits}}.{cents:02d}"


@dataclass
class ReportLine:
    ein: str
    txpd: str
    code: str
    text: str
    quarter: int
    underpayment: Decimal
    amount: Decimal

    def render(self) -> str:
        return (
            "ESTPEN"
            + "  "
            + self.ein
            + " "
            + self.txpd
            + "  "
            + self.code.ljust(4)[:4]
            + "  "
            + self.text.ljust(24)[:24]
            + "  "
            + str(self.quarter)
            + " "
            + edit_z(self.underpayment, 8)
            + " "
            + edit_z(self.amount, 7)
            + " " * 35
        )


@dataclass
class Result:
    records: bytes
    report: list[str]
    read_count: int
    written_count: int
    assessed_count: int

    def stdout(self) -> str:
        return (
            f"ESTPEN  READ    {self.read_count % 10 ** 6:06d}\n"
            f"ESTPEN  WRITTEN {self.written_count % 10 ** 6:06d}\n"
            f"ESTPEN  ASSESSED{self.assessed_count % 10 ** 6:06d}\n"
        )


def _process_record(record: bytearray, report: list[ReportLine]) -> bool:
    """2100-EST.  Returns True when a penalty was assessed."""
    wacc = Decimal("0.00")
    wrap = unpack_comp3(bytes(record[slice(*OFF_ASSD)]), 2)
    if wrap < 500:
        return False

    wrqi = truncate(wrap * Decimal("0.25"), 11)
    wpdi = truncate(unpack_comp3(bytes(record[slice(*OFF_DEP)]), 2) * Decimal("0.25"), 11)
    wund = truncate(wrqi - wpdi, 11)
    if not wund > 0:
        return False

    ein = record[slice(*OFF_EIN)].decode("ascii")
    txpd = record[slice(*OFF_TXPD)].decode("ascii")
    for quarter in (1, 2, 3, 4):
        wqdy = QUARTER_DAYS[quarter]
        wqam = rounded(wund * WQRT * wqdy / Decimal(30), 9)
        wacc = truncate(wacc + wqam, 9)
        report.append(
            ReportLine(ein, txpd, "E601", "INSTALLMENT SHORTFALL", quarter, wund, wqam)
        )

    pftp = unpack_comp3(bytes(record[slice(*OFF_PFTP)]), 2)
    record[slice(*OFF_PFTP)] = pack_comp3(truncate(pftp + wacc, 9), 11, 2)
    return True


def run(modin: bytes) -> Result:
    """0000-MAIN / 2000-PROC over the MODPEN generation."""
    out = bytearray()
    report: list[ReportLine] = []
    read_count = written_count = assessed_count = 0

    for offset in range(0, len(modin), RECORD_LEN):
        record = bytearray(modin[offset:offset + RECORD_LEN])
        if len(record) != RECORD_LEN:
            break
        read_count += 1
        if record[slice(*OFF_MFT)].decode("ascii") == "02":
            if _process_record(record, report):
                assessed_count += 1
        out += record
        written_count += 1

    return Result(bytes(out), [line.render() for line in report],
                  read_count, written_count, assessed_count)


def run_files(modin_path: Path, modout_path: Path, report_path: Path) -> Result:
    result = run(Path(modin_path).read_bytes())
    Path(modout_path).write_bytes(result.records)
    # ORGANIZATION IS LINE SEQUENTIAL strips trailing blanks from each line.
    Path(report_path).write_text(
        "".join(line.rstrip() + "\n" for line in result.report)
    )
    return result


def main(argv: list[str]) -> int:
    modin = Path(argv[1]) if len(argv) > 1 else Path("data/MODPEN.dat")
    modout = Path(argv[2]) if len(argv) > 2 else Path("data/MODEST.dat")
    report = Path(argv[3]) if len(argv) > 3 else Path("data/ESTPEN.rpt")
    sys.stdout.write(run_files(modin, modout, report).stdout())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
