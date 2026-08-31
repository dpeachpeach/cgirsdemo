"""Python port of the COBOL program OFFSET (step 090, IRM 21.4.6).

Characterization port: the COBOL in src/OFFSET.cbl is the specification.
Behaviour is reproduced as observed, defects included.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import List, Sequence, Tuple

MOD_RECLEN = 150
DEBT_RECLEN = 39
DEBT_TABLE_LIMIT = 500

CENT = Decimal("0.01")


def unpack_decimal(raw: bytes, scale: int) -> Decimal:
    """Decode a COMP-3 (packed decimal) field."""
    digits = []
    for byte in raw[:-1]:
        digits.append(byte >> 4)
        digits.append(byte & 0x0F)
    digits.append(raw[-1] >> 4)
    sign_nibble = raw[-1] & 0x0F
    value = Decimal(0)
    for digit in digits:
        value = value * 10 + digit
    if scale:
        value = value.scaleb(-scale)
    if sign_nibble == 0x0D:
        value = -value
    return value


def pack_decimal(value: Decimal, digits: int, scale: int, signed: bool = True) -> bytes:
    """Encode a Decimal as a COMP-3 field of `digits` digits."""
    scaled = int(value.scaleb(scale).to_integral_value(rounding="ROUND_DOWN"))
    negative = scaled < 0
    text = str(abs(scaled)).zfill(digits)[-digits:]
    if not signed:
        sign_nibble = "F"
    else:
        sign_nibble = "D" if negative else "C"
    nibbles = text + sign_nibble
    if len(nibbles) % 2:
        nibbles = "0" + nibbles
    return bytes.fromhex(nibbles)


@dataclass
class ModuleRecord:
    raw: bytes

    @property
    def ein(self) -> str:
        return self.raw[0:9].decode("ascii")

    @property
    def mft(self) -> str:
        return self.raw[9:11].decode("ascii")

    @property
    def txpd(self) -> str:
        return self.raw[11:17].decode("ascii")

    @property
    def frz_o(self) -> str:
        return self.raw[65:66].decode("ascii")

    @property
    def assd(self) -> Decimal:
        return unpack_decimal(self.raw[78:85], 2)

    @property
    def dep(self) -> Decimal:
        return unpack_decimal(self.raw[85:92], 2)

    @property
    def crd(self) -> Decimal:
        return unpack_decimal(self.raw[92:99], 2)

    @property
    def pftd(self) -> Decimal:
        return unpack_decimal(self.raw[99:105], 2)

    @property
    def pftf(self) -> Decimal:
        return unpack_decimal(self.raw[105:111], 2)

    @property
    def pftp(self) -> Decimal:
        return unpack_decimal(self.raw[111:117], 2)

    @property
    def interest(self) -> Decimal:
        return unpack_decimal(self.raw[117:123], 2)


@dataclass
class Debt:
    ein: str
    src: str
    mft: str
    txpd: str
    balance: Decimal


def _numeric(text: str) -> Decimal:
    """DISPLAY numeric field read from a text fixture; blanks read as zero."""
    stripped = text.strip()
    if not stripped:
        return Decimal(0)
    return Decimal(stripped)


def load_debts(path: Path) -> Tuple[List[Debt], int]:
    """1000-LOAD.  Entries past the 500-occurrence table are dropped."""
    table: List[Debt] = []
    count = 0
    with open(path, "r", encoding="ascii", newline="") as handle:
        for line in handle:
            record = line.rstrip("\n").rstrip("\r").ljust(DEBT_RECLEN)[:DEBT_RECLEN]
            if count >= DEBT_TABLE_LIMIT:
                continue
            count += 1
            table.append(
                Debt(
                    ein=record[0:9],
                    src=record[9:11],
                    mft=record[11:13],
                    txpd=record[13:19],
                    balance=_numeric(record[19:32]).scaleb(-2).quantize(CENT),
                )
            )
    return table, count


def read_modules(path: Path) -> List[ModuleRecord]:
    data = path.read_bytes()
    return [
        ModuleRecord(data[i : i + MOD_RECLEN])
        for i in range(0, len(data) - MOD_RECLEN + 1, MOD_RECLEN)
    ]


def _edit_amount(value: Decimal) -> str:
    """PIC ZZZZZZZZ9.99 - nine integer digits, high-order digits truncated."""
    cents = int(value.scaleb(2).to_integral_value(rounding="ROUND_DOWN"))
    cents = abs(cents) % 10 ** 11
    whole, frac = divmod(cents, 100)
    integral = str(whole)
    if len(integral) < 9:
        integral = integral.rjust(9)
    return "%s.%02d" % (integral, frac)


def report_line(ein: str, mft: str, txpd: str, code: str, text: str,
                src: str, amount: Decimal, remaining: Decimal) -> str:
    line = (
        "OFFSET"
        + "  "
        + ein
        + " "
        + mft
        + " "
        + txpd
        + "  "
        + code.ljust(4)
        + "  "
        + text.ljust(24)
        + "  "
        + src.ljust(2)
        + " "
        + _edit_amount(amount)
        + " "
        + _edit_amount(remaining)
        + " " * 20
    )
    return line.rstrip()


def process(modules: Sequence[ModuleRecord], debts: List[Debt]) -> Tuple[List[bytes], List[str], dict]:
    """2000-PROC / 2100-OFF / 2200-SCAN."""
    out_records: List[bytes] = []
    report: List[str] = []
    counters = {"read": 0, "written": 0, "applied": 0, "suppressed": 0}

    for module in modules:
        counters["read"] += 1
        liability = module.assd + module.pftd + module.pftf + module.pftp
        available = module.dep + module.crd + module.interest - liability

        if available > 0:
            if module.frz_o == "O":
                counters["suppressed"] += 1
                report.append(
                    report_line(module.ein, module.mft, module.txpd, "G901",
                                "OFFSET FROZEN", "", Decimal(0), available)
                )
            else:
                for src in ("BM", "IM", "DM"):
                    for debt in debts:
                        if (debt.ein == module.ein and debt.src == src
                                and debt.balance > 0 and available > 0):
                            applied = debt.balance if debt.balance < available else available
                            debt.balance -= applied
                            available -= applied
                            counters["applied"] += 1
                            report.append(
                                report_line(module.ein, module.mft, module.txpd,
                                            "G902", "OFFSET APPLIED", src,
                                            applied, available)
                            )

        out_records.append(module.raw)
        counters["written"] += 1

    return out_records, report, counters


def counter_lines(debt_count: int, counters: dict) -> List[str]:
    return [
        "OFFSET  DEBTS   +%05d" % debt_count,
        "OFFSET  READ    %06d" % counters["read"],
        "OFFSET  WRITTEN %06d" % counters["written"],
        "OFFSET  APPLIED %06d" % counters["applied"],
        "OFFSET  SUPPRESS%06d" % counters["suppressed"],
    ]


def run(modin: Path, debtin: Path, modout: Path, rptout: Path) -> List[str]:
    debts, debt_count = load_debts(Path(debtin))
    modules = read_modules(Path(modin))
    out_records, report, counters = process(modules, debts)
    Path(modout).write_bytes(b"".join(out_records))
    with open(rptout, "w", encoding="ascii", newline="\n") as handle:
        for line in report:
            handle.write(line + "\n")
    return counter_lines(debt_count, counters)


def main(argv: Sequence[str]) -> int:
    modin = Path(argv[1]) if len(argv) > 1 else Path("data/MODINT.dat")
    debtin = Path(argv[2]) if len(argv) > 2 else Path("data/DEBTS.txt")
    modout = Path(argv[3]) if len(argv) > 3 else Path("data/MODOFF.dat")
    rptout = Path(argv[4]) if len(argv) > 4 else Path("data/OFFSET.rpt")
    for line in run(modin, debtin, modout, rptout):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
