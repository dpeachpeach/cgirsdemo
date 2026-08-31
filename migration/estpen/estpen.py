"""ESTPEN — corporate estimated tax penalty, step 060 of the BMF nightly cycle.

Port of src/ESTPEN.cbl. Reads data/MODPEN.dat, writes data/MODEST.dat and
data/ESTPEN.rpt. ESTPEN CALLs no subprogram.

The COBOL is the specification. Where the COBOL produces a surprising value
(silent high-order truncation of report fields, silent wraparound on ADD into
BMF-PFTP) this module reproduces it; see the characterization tests.
"""

from __future__ import annotations

import sys
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, getcontext
from pathlib import Path

getcontext().prec = 60

RECORD_LENGTH = 150

# copybooks/BMFMOD.cpy displacements, zero-relative
OFF_EIN = (0, 9)
OFF_MFT = (9, 11)
OFF_TXPD = (11, 17)
OFF_ASSD = (78, 85)     # S9(11)V99 COMP-3, 7 bytes
OFF_DEP = (85, 92)      # S9(11)V99 COMP-3, 7 bytes
OFF_PFTP = (111, 117)   # S9(9)V99  COMP-3, 6 bytes

QUARTER_DAYS = {1: 275, 2: 183, 3: 92, 4: 30}
WQRT = Decimal("0.0008")

CENTS = Decimal("0.01")


def unpack_comp3(raw: bytes, scale: int) -> Decimal:
    """Decode a packed-decimal (COMP-3) field."""
    nibbles = []
    for byte in raw:
        nibbles.append(byte >> 4)
        nibbles.append(byte & 0x0F)
    sign = nibbles.pop()
    value = Decimal("".join(str(n) for n in nibbles)).scaleb(-scale)
    if sign in (0x0B, 0x0D):
        value = -value
    return value


def pack_comp3(value: Decimal, digits: int, scale: int) -> bytes:
    """Encode a signed packed-decimal (COMP-3) field of `digits` total digits."""
    magnitude = value.copy_abs().quantize(Decimal(1).scaleb(-scale), rounding=ROUND_DOWN)
    text = "".join(c for c in str(magnitude) if c.isdigit()).rjust(digits, "0")[-digits:]
    nibbles = text + ("d" if value < 0 else "c")
    if len(nibbles) % 2:
        nibbles = "0" + nibbles
    return bytes.fromhex(nibbles)


def store(value: Decimal, int_digits: int, scale: int, rounded: bool = False) -> Decimal:
    """Store `value` into a PIC S9(int_digits)V9(scale) field.

    COBOL keeps the low-order digits and silently discards the overflow when
    there is no ON SIZE ERROR clause, and truncates rather than rounds unless
    ROUNDED is written.
    """
    quantum = Decimal(1).scaleb(-scale)
    rounding = ROUND_HALF_UP if rounded else ROUND_DOWN
    magnitude = value.copy_abs().quantize(quantum, rounding=rounding)
    modulus = Decimal(1).scaleb(int_digits)
    if magnitude >= modulus:
        magnitude = magnitude % modulus
    return -magnitude if value < 0 else magnitude


def edit_z(value: Decimal, int_digits: int) -> str:
    """MOVE into a PIC Z...Z9.99 numeric-edited field.

    Zero-suppresses every integer position but the last, drops the sign, and
    truncates high-order digits that do not fit.
    """
    magnitude = store(value.copy_abs(), int_digits, 2)
    digits = "".join(c for c in str(magnitude) if c.isdigit()).rjust(int_digits + 2, "0")
    whole, cents = digits[:int_digits], digits[int_digits:]
    suppressible = list(whole[:-1])
    for i, ch in enumerate(suppressible):
        if ch != "0":
            break
        suppressible[i] = " "
    return "".join(suppressible) + whole[-1] + "." + cents


class Module:
    """A 150-byte BMF module record; untouched bytes pass through verbatim."""

    def __init__(self, raw: bytes) -> None:
        if len(raw) != RECORD_LENGTH:
            raise ValueError("module record is %d bytes, expected %d"
                             % (len(raw), RECORD_LENGTH))
        self.raw = bytearray(raw)

    @property
    def ein(self) -> str:
        return self.raw[slice(*OFF_EIN)].decode("ascii")

    @property
    def mft(self) -> int:
        return int(self.raw[slice(*OFF_MFT)].decode("ascii"))

    @property
    def txpd(self) -> str:
        return self.raw[slice(*OFF_TXPD)].decode("ascii")

    @property
    def assd(self) -> Decimal:
        return unpack_comp3(bytes(self.raw[slice(*OFF_ASSD)]), 2)

    @property
    def dep(self) -> Decimal:
        return unpack_comp3(bytes(self.raw[slice(*OFF_DEP)]), 2)

    @property
    def pftp(self) -> Decimal:
        return unpack_comp3(bytes(self.raw[slice(*OFF_PFTP)]), 2)

    @pftp.setter
    def pftp(self, value: Decimal) -> None:
        self.raw[slice(*OFF_PFTP)] = pack_comp3(value, 11, 2)

    def bytes(self) -> bytes:
        return bytes(self.raw)


def report_line(module: Module, quarter: int, wund: Decimal, wqam: Decimal) -> str:
    """Build one ERPT record. LINE SEQUENTIAL strips the trailing FILLER."""
    return (
        "ESTPEN" + "  "
        + module.ein + " "
        + module.txpd + "  "
        + "E601" + "  "
        + "INSTALLMENT SHORTFALL".ljust(24) + "  "
        + str(quarter) + " "
        + edit_z(wund, 8) + " "
        + edit_z(wqam, 7)
    )


def assess(module: Module, report: list[str]) -> bool:
    """2100-EST. Returns True when a penalty was assessed (counter E3)."""
    wacc = Decimal("0.00")
    wrap = store(module.assd, 11, 2)
    if wrap < 500:
        return False
    wrqi = store(wrap * Decimal("0.25"), 11, 2)
    wpdi = store(module.dep * Decimal("0.25"), 11, 2)
    wund = store(wrqi - wpdi, 11, 2)
    if not wund > 0:
        return False
    for quarter in (1, 2, 3, 4):
        wqdy = QUARTER_DAYS[quarter]
        wqam = store(wund * WQRT * wqdy / 30, 9, 2, rounded=True)
        wacc = store(wacc + wqam, 9, 2)
        report.append(report_line(module, quarter, wund, wqam))
    module.pftp = store(module.pftp + wacc, 9, 2)
    return True


class Counters:
    def __init__(self) -> None:
        self.read = 0
        self.written = 0
        self.assessed = 0

    def display(self) -> str:
        return ("ESTPEN  READ    %06d\n"
                "ESTPEN  WRITTEN %06d\n"
                "ESTPEN  ASSESSED%06d\n" % (self.read, self.written, self.assessed))


def process(modin: bytes) -> tuple[bytes, str, Counters]:
    """Run ESTPEN over a MODPEN.dat image. Returns (MODEST.dat, ESTPEN.rpt, counters)."""
    counters = Counters()
    report: list[str] = []
    out = bytearray()
    for offset in range(0, len(modin), RECORD_LENGTH):
        module = Module(modin[offset:offset + RECORD_LENGTH])
        counters.read += 1
        if module.mft == 2 and assess(module, report):
            counters.assessed += 1
        out += module.bytes()
        counters.written += 1
    text = "".join(line + "\n" for line in report)
    return bytes(out), text, counters


def main(argv: list[str]) -> int:
    modin = Path(argv[1] if len(argv) > 1 else "data/MODPEN.dat")
    modot = Path(argv[2] if len(argv) > 2 else "data/MODEST.dat")
    esrpt = Path(argv[3] if len(argv) > 3 else "data/ESTPEN.rpt")
    out, text, counters = process(modin.read_bytes())
    modot.write_bytes(out)
    esrpt.write_text(text)
    sys.stdout.write(counters.display())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
