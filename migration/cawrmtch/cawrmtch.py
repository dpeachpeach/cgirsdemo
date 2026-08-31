"""Python port of CAWRMTCH (step 100) — Combined Annual Wage Reporting match.

Behavioral port of src/CAWRMTCH.cbl. Reads the offset-generation module master
(MODOFF.dat, 150-byte fixed records laid out by copybooks/BMFMOD.cpy) and the
SSA W-2 totals (CAWRW2.txt, 44-byte lines), and writes data/CAWRMTCH.rpt.

Arithmetic uses Decimal with COBOL semantics: COMPUTE without ROUNDED
truncates toward zero at the receiving field's scale, and every MOVE into a
smaller PIC truncates high-order digits.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

MOD_RECORD_LEN = 150
W2_RECORD_LEN = 44
KEY_LEN = 13
HIGH_VALUES = b"\xff" * KEY_LEN

# copybooks/BMFMOD.cpy displacements (zero-relative)
OFF_EIN = 0
OFF_MFT = 9
OFF_TXPD = 11
OFF_ASSD = 78
LEN_ASSD = 7  # PIC S9(11)V99 COMP-3


def unpack_comp3(raw: bytes, scale: int) -> Decimal:
    """Decode a packed-decimal (COMP-3) field into a Decimal."""
    digits = "".join(f"{b >> 4:x}{b & 0x0F:x}" for b in raw)
    sign_nibble = int(digits[-1], 16)
    digits = digits[:-1]
    value = Decimal(digits).scaleb(-scale)
    if sign_nibble in (0x0B, 0x0D):
        value = -value
    return value


def truncate(value: Decimal, int_digits: int, scale: int) -> Decimal:
    """Store into PIC S9(int_digits)V(scale): truncate low and high order."""
    quantum = Decimal(1).scaleb(-scale)
    value = value.quantize(quantum, rounding="ROUND_DOWN")
    modulus = Decimal(10) ** int_digits
    sign = -1 if value < 0 else 1
    magnitude = abs(value) % modulus
    return sign * magnitude


def edit_unsigned(value: Decimal) -> str:
    """PIC ZZZZZZZZ9.99 — 12 characters, no sign, high-order zeros suppressed."""
    magnitude = truncate(abs(value), 9, 2)
    text = f"{magnitude:.2f}"
    return text.rjust(12)


def edit_signed(value: Decimal) -> str:
    """PIC ZZZZZZZZ9.99- — 12 characters plus a trailing sign position."""
    return edit_unsigned(value) + ("-" if value < 0 else " ")


@dataclass
class Module:
    key: bytes
    assd: Decimal


@dataclass
class W2:
    key: bytes
    ein: str
    year: str
    wage: Decimal
    whld: Decimal
    doc: str


def read_modules(path: Path) -> Iterator[Module]:
    """8100-RDMOD: sequential read, skipping every module whose MFT is not 01."""
    with path.open("rb") as handle:
        while True:
            record = handle.read(MOD_RECORD_LEN)
            if len(record) < MOD_RECORD_LEN:
                return
            if record[OFF_MFT:OFF_MFT + 2] != b"01":
                continue
            key = record[OFF_EIN:OFF_EIN + 9] + record[OFF_TXPD:OFF_TXPD + 4]
            assd = unpack_comp3(record[OFF_ASSD:OFF_ASSD + LEN_ASSD], 2)
            yield Module(key=key, assd=assd)


def read_w2(path: Path) -> Iterator[W2]:
    """8200-RDW2: line sequential read into the 44-byte W2REC layout."""
    with path.open("r", encoding="ascii") as handle:
        for line in handle:
            line = line.rstrip("\n").ljust(W2_RECORD_LEN)[:W2_RECORD_LEN]
            ein = line[0:9]
            year = line[9:13]
            wage = Decimal(line[13:26]).scaleb(-2)
            whld = Decimal(line[26:39]).scaleb(-2)
            yield W2(
                key=(ein + year).encode("ascii"),
                ein=ein,
                year=year,
                wage=wage,
                whld=whld,
                doc=line[39:44],
            )


class Report:
    """CRPT record image, built field by field the way the COBOL MOVEs it."""

    def __init__(self) -> None:
        self.ein = "0" * 9
        self.year = "0" * 4
        self.code = " " * 4
        self.text = " " * 24
        self.w2 = Decimal(0)
        self.liability = Decimal(0)
        self.diff = Decimal(0)

    def line(self) -> str:
        record = (
            "CAWRMTCH" + "  "
            + self.ein + " "
            + self.year + "  "
            + self.code.ljust(4)[:4] + "  "
            + self.text.ljust(24)[:24] + "  "
            + edit_unsigned(self.w2) + " "
            + edit_unsigned(self.liability) + " "
            + edit_signed(self.diff)
            + " " * 15
        )
        return record.ljust(120)[:120].rstrip()


class Counters:
    def __init__(self) -> None:
        self.groups_941 = 0   # C1
        self.w2_records = 0   # C2
        self.matched = 0      # C3
        self.w2_only = 0      # C4
        self.discrepant = 0   # C5

    def as_dict(self) -> dict:
        return {
            "groups_941": self.groups_941,
            "w2_records": self.w2_records,
            "matched": self.matched,
            "w2_only": self.w2_only,
            "discrepant": self.discrepant,
        }

    def display_lines(self) -> List[str]:
        return [
            f"CAWRMTCH 941 GRP {self.groups_941:06d}",
            f"CAWRMTCH W2  REC {self.w2_records:06d}",
            f"CAWRMTCH MATCHED {self.matched:06d}",
            f"CAWRMTCH W2 ONLY {self.w2_only:06d}",
            f"CAWRMTCH DISCREP {self.discrepant:06d}",
        ]


def run(mod_path: Path, w2_path: Path) -> Tuple[List[str], Counters]:
    """0000-MAIN: drive the three-way merge and return report lines plus counters."""
    counters = Counters()
    lines: List[str] = []
    rpt = Report()

    modules = read_modules(Path(mod_path))
    w2_records = read_w2(Path(w2_path))

    module: Optional[Module] = next(modules, None)
    mkey = module.key if module else HIGH_VALUES
    meof = module is None

    w2: Optional[W2] = next(w2_records, None)
    if w2 is None:
        weof = True
        wkey = HIGH_VALUES
    else:
        weof = False
        wkey = w2.key
        counters.w2_records += 1
    hold = w2

    def read_module() -> None:
        nonlocal module, mkey, meof
        module = next(modules, None)
        if module is None:
            meof = True
            mkey = HIGH_VALUES
        else:
            mkey = module.key

    def read_w2_record() -> None:
        nonlocal w2, wkey, weof, hold
        w2 = next(w2_records, None)
        if w2 is None:
            weof = True
            wkey = HIGH_VALUES
        else:
            wkey = w2.key
            counters.w2_records += 1
            hold = w2

    def group() -> Tuple[bytes, Decimal, int]:
        """3000-GRP: control break over every MFT 01 module for the key."""
        nonlocal mkey
        hkey = mkey
        liability = Decimal(0)
        count = 0
        while not meof and mkey == hkey:
            liability = truncate(liability + module.assd, 11, 2)
            count += 1
            read_module()
        counters.groups_941 += 1
        return hkey, liability, count

    def compare(hkey: bytes, liability: Decimal) -> None:
        """4000-CMP: tolerance test against the held W-2 withholding."""
        diff = truncate(hold.whld - liability, 11, 2)
        tolerance = truncate(liability * Decimal("0.01"), 11, 2)
        if tolerance < 100:
            tolerance = Decimal(100)
        rpt.ein = hold.ein
        rpt.year = hkey[9:13].decode("ascii")
        rpt.w2 = hold.whld
        rpt.liability = liability
        rpt.diff = diff
        if abs(diff) <= tolerance:
            counters.matched += 1
            rpt.code = "C001"
            rpt.text = "IN BALANCE"
        else:
            counters.discrepant += 1
            if diff > 0:
                rpt.code = "C002"
                rpt.text = "W2 EXCEEDS 941 LIABILITY"
            else:
                rpt.code = "C003"
                rpt.text = "941 EXCEEDS W2 REPORTED"
        lines.append(rpt.line())

    def only_941(hkey: bytes, liability: Decimal) -> None:
        """4100-941ONLY: posted liability with no SSA W-2 data."""
        counters.discrepant += 1
        rpt.ein = hkey[0:9].decode("ascii")
        rpt.year = hkey[9:13].decode("ascii")
        rpt.code = "C004"
        rpt.text = "NO W2 DATA FROM SSA"
        rpt.w2 = Decimal(0)
        rpt.liability = liability
        rpt.diff = truncate(Decimal(0) - liability, 11, 2)
        lines.append(rpt.line())

    def only_w2() -> None:
        """4200-W2ONLY: W-2 filed with no matching MFT 01 module."""
        counters.w2_only += 1
        rpt.ein = hold.ein
        rpt.year = hold.year
        rpt.code = "C005"
        rpt.text = "W2 FILED - NO 941 MODULE"
        rpt.w2 = hold.whld
        rpt.liability = Decimal(0)
        rpt.diff = hold.whld
        lines.append(rpt.line())

    while not (meof and weof):
        if mkey < wkey:
            hkey, liability, _ = group()
            only_941(hkey, liability)
        elif mkey > wkey:
            only_w2()
            read_w2_record()
        else:
            hkey, liability, _ = group()
            compare(hkey, liability)
            read_w2_record()

    return lines, counters


def main(argv: List[str]) -> int:
    mod_path = Path(argv[1]) if len(argv) > 1 else Path("data/MODOFF.dat")
    w2_path = Path(argv[2]) if len(argv) > 2 else Path("data/CAWRW2.txt")
    rpt_path = Path(argv[3]) if len(argv) > 3 else Path("data/CAWRMTCH.rpt")
    lines, counters = run(mod_path, w2_path)
    rpt_path.write_text("".join(line + "\n" for line in lines), encoding="ascii")
    for line in counters.display_lines():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
