"""Python port of src/CAWRMTCH.cbl -- Combined Annual Wage Reporting match.

Step 100 of the nightly cycle: a sequential match of the SSA W-2 totals in
data/CAWRW2.txt against the posted Form 941 liability accumulated from the
MFT 01 modules in data/MODOFF.dat, both in EIN / tax-year sequence.

The COBOL is the specification. Behaviour that looks wrong here is wrong in
the same way in the COBOL; see reports/PORT-CAWRMTCH-<date>.md for the
proposed fixes that were deliberately not applied.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from typing import BinaryIO, Iterator, NamedTuple

MOD_RECORD_LEN = 150
W2_RECORD_LEN = 44
HIGH_VALUES = b"\xff" * 13

# S9(11)V99 COMP-3: eleven integer digits, two decimals, no ON SIZE ERROR.
S11V2_MODULUS = Decimal(10) ** 11
CENT = Decimal("0.01")

# BMF-MOD-REC field displacements, from copybooks/BMFMOD.cpy.
BMF_EIN = slice(0, 9)
BMF_MFT = slice(9, 11)
BMF_TXPD = slice(11, 17)
BMF_ASSD = slice(78, 85)


class CawrCounters(NamedTuple):
    """The five DISPLAY counters 0000-MAIN writes at end of job."""

    groups_941: int
    w2_records: int
    matched: int
    w2_only: int
    discrepancies: int

    def render(self) -> str:
        return (
            f"CAWRMTCH 941 GRP {self.groups_941:06d}\n"
            f"CAWRMTCH W2  REC {self.w2_records:06d}\n"
            f"CAWRMTCH MATCHED {self.matched:06d}\n"
            f"CAWRMTCH W2 ONLY {self.w2_only:06d}\n"
            f"CAWRMTCH DISCREP {self.discrepancies:06d}\n"
        )


def unpack_comp3(raw: bytes, scale: int) -> Decimal:
    """Decode a packed-decimal field: two digits per byte, sign in the low nibble."""
    nibbles = raw.hex()
    value = Decimal(nibbles[:-1])
    if scale:
        value = value.scaleb(-scale)
    return -value if nibbles[-1] in "bd" else value


def truncate_s11v2(value: Decimal) -> Decimal:
    """Store into PIC S9(11)V99: truncate toward zero, drop high-order overflow."""
    value = value.quantize(CENT, rounding="ROUND_DOWN")
    integer = value.to_integral_value(rounding="ROUND_DOWN")
    if abs(integer) >= S11V2_MODULUS:
        wrapped = abs(integer) % S11V2_MODULUS
        value = (wrapped if integer >= 0 else -wrapped) + (value - integer)
    return value


def edit_zz9_99(value: Decimal) -> str:
    """PIC ZZZZZZZZ9.99 -- unsigned, nine integer digits, leading zero suppression."""
    digits = abs(value).quantize(CENT, rounding="ROUND_DOWN")
    integer = int(digits.to_integral_value(rounding="ROUND_DOWN")) % 1000000000
    cents = int((digits - digits.to_integral_value(rounding="ROUND_DOWN")) * 100)
    return f"{integer:9d}.{cents:02d}"


def edit_zz9_99_trailing_sign(value: Decimal) -> str:
    """PIC ZZZZZZZZ9.99- -- trailing minus for negatives, trailing space otherwise."""
    return edit_zz9_99(value) + ("-" if value < 0 else " ")


class ModuleReader:
    """8100-RDMOD: advance to the next MFT 01 module, HIGH-VALUES at end of file."""

    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self.eof = False
        self.key = b""
        self.assessed = Decimal(0)

    def read(self) -> None:
        while not self.eof:
            record = self._stream.read(MOD_RECORD_LEN)
            if len(record) < MOD_RECORD_LEN:
                self.eof = True
                self.key = HIGH_VALUES
                return
            if record[BMF_MFT] == b"01":
                self.key = record[BMF_EIN] + record[BMF_TXPD][:4]
                self.assessed = unpack_comp3(record[BMF_ASSD], 2)
                return


class W2Reader:
    """8200-RDW2: read one 44-byte SSA total, HIGH-VALUES at end of file."""

    def __init__(self, lines: Iterator[bytes]) -> None:
        self._lines = lines
        self.eof = False
        self.key = b""
        self.count = 0
        self.ein = b"000000000"
        self.year = b"0000"
        self.withheld = Decimal(0)

    def read(self) -> None:
        line = next(self._lines, None)
        if line is None:
            self.eof = True
            self.key = HIGH_VALUES
            return
        record = line.ljust(W2_RECORD_LEN, b" ")[:W2_RECORD_LEN]
        self.count += 1
        self.ein = record[0:9]
        self.year = record[9:13]
        self.key = self.ein + self.year
        self.withheld = Decimal(_digits(record[26:39])).scaleb(-2)


def _digits(raw: bytes) -> str:
    """Numeric DISPLAY field: blanks in an unedited PIC 9 field read as zero."""
    return "".join(c if c.isdigit() else "0" for c in raw.decode("latin-1"))


def _report_line(ein: bytes, year: bytes, code: str, text: str,
                 w2_amount: Decimal, liability: Decimal, difference: Decimal) -> str:
    record = (
        "CAWRMTCH"
        + "  "
        + ein.decode("latin-1")
        + " "
        + year.decode("latin-1")
        + "  "
        + code
        + "  "
        + text.ljust(24)[:24]
        + "  "
        + edit_zz9_99(w2_amount)
        + " "
        + edit_zz9_99(liability)
        + " "
        + edit_zz9_99_trailing_sign(difference)
        + " " * 15
    )
    return record.rstrip(" ")


def run(modin_path: str, w2in_path: str, report_path: str) -> CawrCounters:
    """0000-MAIN: drive the three-way match and write data/CAWRMTCH.rpt."""
    groups_941 = w2_only = matched = discrepancies = 0
    lines: list[bytes] = []
    with open(w2in_path, "rb") as w2_file:
        lines = [ln.rstrip(b"\r\n") for ln in w2_file.readlines()]

    with open(modin_path, "rb") as mod_file, open(report_path, "w",
                                                  newline="\n") as report:
        modules = ModuleReader(mod_file)
        w2s = W2Reader(iter(lines))
        modules.read()
        w2s.read()

        while not (modules.eof and w2s.eof):
            if modules.key < w2s.key:
                # 3000-GRP then 4100-941ONLY: liability with no SSA counterpart.
                hold_key, liability = _accumulate_group(modules)
                groups_941 += 1
                discrepancies += 1
                report.write(_report_line(
                    hold_key[0:9], hold_key[9:13], "C004",
                    "NO W2 DATA FROM SSA", Decimal(0), liability,
                    truncate_s11v2(Decimal(0) - liability)) + "\n")
            elif modules.key > w2s.key:
                # 4200-W2ONLY: SSA total with no 941 module.
                w2_only += 1
                report.write(_report_line(
                    w2s.ein, w2s.year, "C005", "W2 FILED - NO 941 MODULE",
                    w2s.withheld, Decimal(0), w2s.withheld) + "\n")
                w2s.read()
            else:
                # 3000-GRP then 4000-CMP: matched EIN and tax year.
                hold_key, liability = _accumulate_group(modules)
                groups_941 += 1
                difference = truncate_s11v2(w2s.withheld - liability)
                tolerance = truncate_s11v2(liability * Decimal("0.01"))
                if tolerance < 100:
                    tolerance = Decimal(100)
                if abs(difference) <= tolerance:
                    matched += 1
                    code, text = "C001", "IN BALANCE"
                else:
                    discrepancies += 1
                    if difference > 0:
                        code, text = "C002", "W2 EXCEEDS 941 LIABILITY"
                    else:
                        code, text = "C003", "941 EXCEEDS W2 REPORTED"
                report.write(_report_line(
                    w2s.ein, hold_key[9:13], code, text,
                    w2s.withheld, liability, difference) + "\n")
                w2s.read()

    return CawrCounters(groups_941 % 1000000, w2s.count % 1000000,
                        matched % 1000000, w2_only % 1000000,
                        discrepancies % 1000000)


def _accumulate_group(modules: ModuleReader) -> tuple[bytes, Decimal]:
    """3000-GRP: sum BMF-ASSD across every MFT 01 module for one EIN and year."""
    hold_key = modules.key
    liability = Decimal(0)
    while not modules.eof and modules.key == hold_key:
        liability = truncate_s11v2(liability + modules.assessed)
        modules.read()
    return hold_key, liability


def main(argv: list[str]) -> int:
    modin = argv[1] if len(argv) > 1 else "data/MODOFF.dat"
    w2in = argv[2] if len(argv) > 2 else "data/CAWRW2.txt"
    report = argv[3] if len(argv) > 3 else "data/CAWRMTCH.rpt"
    sys.stdout.write(run(modin, w2in, report).render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
