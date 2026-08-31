"""Python port of src/OFFSET.cbl (pipeline step 090, refund offset).

Characterization port: behaviour is defined by what the COBOL program does,
including its defects. Arithmetic is decimal throughout; COMP-3 fields are
decoded and re-encoded byte for byte so the module record round-trips exactly.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import List, Tuple

MOD_RECORD_LEN = 150
DEBT_RECORD_LEN = 39
DEBT_TABLE_MAX = 500
REPORT_LEN = 120

CENT = Decimal("0.01")


def decode_comp3(data: bytes, scale: int) -> Decimal:
    """Decode a packed-decimal (COMP-3) field."""
    digits = ""
    for byte in data[:-1]:
        digits += str(byte >> 4) + str(byte & 0x0F)
    last = data[-1]
    digits += str(last >> 4)
    sign = -1 if (last & 0x0F) == 0x0D else 1
    value = Decimal(digits) * sign
    return value.scaleb(-scale) if scale else value


def encode_comp3(value: Decimal, digits: int, scale: int, signed: bool = True) -> bytes:
    """Encode a Decimal into a packed-decimal field of `digits` total digits."""
    scaled = int((value * (10 ** scale)).to_integral_value(rounding="ROUND_DOWN"))
    negative = scaled < 0
    text = str(abs(scaled)).rjust(digits, "0")[-digits:]
    if digits % 2 == 0:
        text = "0" + text
    if signed:
        sign_nibble = 0x0D if negative else 0x0C
    else:
        sign_nibble = 0x0F
    out = bytearray()
    for i in range(0, len(text) - 1, 2):
        out.append((int(text[i]) << 4) | int(text[i + 1]))
    out.append((int(text[-1]) << 4) | sign_nibble)
    return bytes(out)


def truncate(value: Decimal, digits: int, scale: int) -> Decimal:
    """Truncate into a PIC S9(digits-scale)V9(scale) field, as a COBOL MOVE does."""
    scaled = int((value * (10 ** scale)).to_integral_value(rounding="ROUND_DOWN"))
    negative = scaled < 0
    scaled = abs(scaled) % (10 ** digits)
    return Decimal(-scaled if negative else scaled).scaleb(-scale)


def edited_z9_99(value: Decimal) -> str:
    """Format into PIC ZZZZZZZZ9.99 (9 integer digits, no sign)."""
    truncated = truncate(value, 11, 2)
    text = "{:.2f}".format(abs(truncated))
    whole, frac = text.split(".")
    return "{}.{}".format(whole.rjust(9), frac)


@dataclass
class ModuleRecord:
    """BMFMOD copybook layout (150 bytes)."""

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
    def frz_o(self) -> str:
        return self.raw[65:66].decode("latin-1")

    @property
    def assd(self) -> Decimal:
        return decode_comp3(self.raw[78:85], 2)

    @property
    def dep(self) -> Decimal:
        return decode_comp3(self.raw[85:92], 2)

    @property
    def crd(self) -> Decimal:
        return decode_comp3(self.raw[92:99], 2)

    @property
    def pftd(self) -> Decimal:
        return decode_comp3(self.raw[99:105], 2)

    @property
    def pftf(self) -> Decimal:
        return decode_comp3(self.raw[105:111], 2)

    @property
    def pftp(self) -> Decimal:
        return decode_comp3(self.raw[111:117], 2)

    @property
    def interest(self) -> Decimal:
        return decode_comp3(self.raw[117:123], 2)


@dataclass
class Debt:
    ein: str
    src: str
    mft: str
    txpd: str
    balance: Decimal


def read_modules(path: Path) -> List[ModuleRecord]:
    data = Path(path).read_bytes()
    return [
        ModuleRecord(data[i:i + MOD_RECORD_LEN])
        for i in range(0, len(data), MOD_RECORD_LEN)
    ]


def load_debts(path: Path) -> List[Debt]:
    """1000-LOAD: records past the 500th are silently dropped."""
    debts: List[Debt] = []
    with open(path, "r", encoding="latin-1") as handle:
        for line in handle:
            line = line.rstrip("\n").ljust(DEBT_RECORD_LEN)[:DEBT_RECORD_LEN]
            if len(debts) >= DEBT_TABLE_MAX:
                continue
            debts.append(
                Debt(
                    ein=line[0:9],
                    src=line[9:11],
                    mft=line[11:13],
                    txpd=line[13:19],
                    balance=truncate(Decimal(line[19:32]).scaleb(-2), 13, 2),
                )
            )
    return debts


def report_line(ein: str, mft: str, txpd: str, code: str, text: str,
                src: str, amount: Decimal, remaining: Decimal) -> str:
    """GRPT layout; LINE SEQUENTIAL output drops trailing spaces."""
    line = (
        "OFFSET" + "  " + ein + " " + mft + " " + txpd + "  "
        + code.ljust(4)[:4] + "  " + text.ljust(24)[:24] + "  "
        + src.ljust(2)[:2] + " " + edited_z9_99(amount) + " "
        + edited_z9_99(remaining) + " " * 20
    ).ljust(REPORT_LEN)
    return line.rstrip(" ")


@dataclass
class Result:
    read: int
    written: int
    applied: int
    suppressed: int
    debts_loaded: int
    report: List[str]
    modules_out: bytes

    def counters(self) -> List[str]:
        return [
            "OFFSET  DEBTS   {}{:05d}".format("+", self.debts_loaded),
            "OFFSET  READ    {:06d}".format(self.read),
            "OFFSET  WRITTEN {:06d}".format(self.written),
            "OFFSET  APPLIED {:06d}".format(self.applied),
            "OFFSET  SUPPRESS{:06d}".format(self.suppressed),
        ]


def offset_module(module: ModuleRecord, debts: List[Debt],
                  counters: List[int]) -> List[str]:
    """2100-OFF / 2200-SCAN for one module record."""
    lines: List[str] = []
    liability = truncate(module.assd + module.pftd + module.pftf + module.pftp, 13, 2)
    available = truncate(module.dep + module.crd + module.interest - liability, 13, 2)
    if not available > 0:
        return lines
    if module.frz_o == "O":
        counters[1] += 1
        lines.append(report_line(module.ein, module.mft, module.txpd, "G901",
                                 "OFFSET FROZEN", "  ", Decimal(0), available))
        return lines
    for source in ("BM", "IM", "DM"):
        for debt in debts:
            if not (debt.ein == module.ein and debt.src == source
                    and debt.balance > 0 and available > 0):
                continue
            applied = debt.balance if debt.balance < available else available
            applied = truncate(applied, 13, 2)
            debt.balance = truncate(debt.balance - applied, 13, 2)
            available = truncate(available - applied, 13, 2)
            counters[0] += 1
            lines.append(report_line(module.ein, module.mft, module.txpd, "G902",
                                     "OFFSET APPLIED", source, applied, available))
    return lines


def run(modin: Path, debts_path: Path) -> Result:
    debts = load_debts(debts_path)
    modules = read_modules(modin)
    counters = [0, 0]
    report: List[str] = []
    out = bytearray()
    for module in modules:
        report.extend(offset_module(module, debts, counters))
        # OFFSET writes the module record through unchanged: the applied
        # offset is never subtracted from the module's credit fields.
        out.extend(module.raw)
    return Result(
        read=len(modules),
        written=len(modules),
        applied=counters[0],
        suppressed=counters[1],
        debts_loaded=len(debts),
        report=report,
        modules_out=bytes(out),
    )


def main(argv: List[str]) -> int:
    modin = Path(argv[1]) if len(argv) > 1 else Path("data/MODINT.dat")
    debts_path = Path(argv[2]) if len(argv) > 2 else Path("data/DEBTS.txt")
    modot = Path(argv[3]) if len(argv) > 3 else Path("data/MODOFF.dat")
    rpt = Path(argv[4]) if len(argv) > 4 else Path("data/OFFSET.rpt")
    result = run(modin, debts_path)
    modot.write_bytes(result.modules_out)
    rpt.write_text("".join(line + "\n" for line in result.report), encoding="latin-1")
    for line in result.counters():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
