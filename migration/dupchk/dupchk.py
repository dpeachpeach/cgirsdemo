"""Python port of src/DUPCHK.cbl (pipeline step 020, IRM 21.7.9).

Reads the BMF module generation and the transaction file, sets the -A freeze on
duplicate filing conditions, applies TC 560 ASED corrections, writes the next
module generation and DUPCHK.rpt.

Behavior is characterized against the COBOL, defects included.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

MOD_LEN = 150
TRN_LEN = 80

# BMFMOD.cpy displacements, zero-relative
BMF_KEY = slice(0, 17)
BMF_EIN = slice(0, 9)
BMF_MFT = slice(9, 11)
BMF_TXPD = slice(11, 17)
BMF_FRZ_A = 58
BMF_ASED = slice(66, 70)  # PIC 9(7) COMP-3
BMF_TCCNT = slice(131, 134)  # PIC 9(3) DISPLAY

# TRANREC.cpy displacements, zero-relative
TRN_KEY = slice(0, 17)
TRN_TC = slice(17, 20)
TRN_DT = slice(20, 27)

# MOVE HIGH-VALUES TO TKEY at transaction end of file
HIGH_VALUES = b"\xff" * 17

REPORT_LEN = 120


def unpack_decimal(raw: bytes, digits: int, scale: int = 0) -> Decimal:
    """Unpack a COMP-3 (packed decimal) field into a Decimal."""
    text = raw.hex()
    sign_nibble = text[-1]
    value = text[:-1][-digits:]
    number = Decimal(value or "0")
    if scale:
        number = number.scaleb(-scale)
    if sign_nibble in ("b", "d"):
        number = -number
    return number


def pack_decimal(value: Decimal, digits: int, signed: bool = False) -> bytes:
    """Pack an integer-valued Decimal into a COMP-3 field of `digits` digits."""
    negative = value < 0
    text = str(abs(value).to_integral_value()).rjust(digits, "0")[-digits:]
    if signed:
        sign_nibble = "d" if negative else "c"
    else:
        sign_nibble = "f"
    nibbles = text + sign_nibble
    if len(nibbles) % 2:
        nibbles = "0" + nibbles
    return bytes.fromhex(nibbles)


def numeric(raw: bytes) -> int:
    """Read a PIC 9(n) DISPLAY field. Spaces read as zero, as MVS does."""
    text = raw.decode("latin-1").strip()
    return int(text) if text.isdigit() else 0


@dataclass
class Counters:
    read: int = 0
    written: int = 0
    freeze: int = 0
    ased_corr: int = 0

    def display_lines(self) -> list[str]:
        return [
            f"DUPCHK  READ    {self.read:06d}",
            f"DUPCHK  WRITTEN {self.written:06d}",
            f"DUPCHK  A FREEZE{self.freeze:06d}",
            f"DUPCHK  ASED COR{self.ased_corr:06d}",
        ]


@dataclass
class Result:
    modules: bytes
    report: list[str]
    counters: Counters


def _report_line(ein: bytes, mft: bytes, txpd: bytes, code: str, text: str,
                 a: int, b: int, c: int) -> str:
    """Build DRPT. Trailing spaces are stripped, as LINE SEQUENTIAL writes."""
    line = (
        "DUPCHK"
        + "  "
        + ein.decode("latin-1")
        + " "
        + mft.decode("latin-1")
        + " "
        + txpd.decode("latin-1")
        + "  "
        + code.ljust(4)[:4]
        + "  "
        + text.ljust(38)[:38]
        + "  "
        + f"{a % 1000:03d}"
        + " "
        + f"{b % 1000:03d}"
        + " "
        + f"{c % 10000000:07d}"
        + " " * 30
    )
    assert len(line) == REPORT_LEN
    return line.rstrip()


class TransactionReader:
    """8100-RDTRN: sequential reader keeping TKEY and TEOF."""

    def __init__(self, data: bytes) -> None:
        self._records = [data[i:i + TRN_LEN] for i in range(0, len(data), TRN_LEN)]
        self._index = 0
        self.record: bytes | None = None
        self.teof = False
        self.tkey = b"\x00" * 17

    def read(self) -> None:
        if self._index >= len(self._records):
            self.teof = True
            self.tkey = HIGH_VALUES
            return
        self.record = self._records[self._index]
        self._index += 1
        self.tkey = self.record[TRN_KEY]


def run(module_data: bytes, transaction_data: bytes) -> Result:
    trn = TransactionReader(transaction_data)
    counters = Counters()
    report: list[str] = []
    out = bytearray()

    trn.read()  # 1000-INIT

    for offset in range(0, len(module_data), MOD_LEN):  # 2000-DRIVE
        record = bytearray(module_data[offset:offset + MOD_LEN])
        counters.read += 1

        # 2100-MOD
        mkey = bytes(record[BMF_KEY])
        c50 = c76 = c77 = c60 = 0
        d60 = d76 = 0
        dupsw = False

        # 2200-SKIP
        while not trn.teof and trn.tkey < mkey:
            trn.read()

        # 2300-GATHER
        while not trn.teof and trn.tkey == mkey:
            tc = numeric(trn.record[TRN_TC])
            dt = numeric(trn.record[TRN_DT])
            if tc == 150:
                c50 += 1
            elif tc == 976:
                c76 += 1
                d76 = dt
            elif tc == 977:
                c77 += 1
            elif tc == 560:
                c60 += 1
                d60 = dt
            tccnt = (numeric(record[BMF_TCCNT]) + 1) % 1000
            record[BMF_TCCNT] = f"{tccnt:03d}".encode("latin-1")
            trn.read()

        # 2400-EVAL
        if c50 > 0 and (c76 > 0 or c77 > 0):
            dupsw = True
        if c50 > 1:
            dupsw = True
        if c76 > 0 and c60 > 0:
            dupsw = False
        if dupsw:
            record[BMF_FRZ_A] = ord("A")
            counters.freeze += 1
            report.append(_report_line(
                bytes(record[BMF_EIN]), bytes(record[BMF_MFT]),
                bytes(record[BMF_TXPD]), "D201",
                "DUP FILING - A FREEZE SET", c76, c77, d76))

        # 2500-ASED
        if c60 > 0:
            w_ased = int(unpack_decimal(bytes(record[BMF_ASED]), 7))
            if d60 > w_ased:
                record[BMF_ASED] = pack_decimal(Decimal(d60), 7)
                counters.ased_corr += 1
                report.append(_report_line(
                    bytes(record[BMF_EIN]), bytes(record[BMF_MFT]),
                    bytes(record[BMF_TXPD]), "D202",
                    "TC 560 ASED CORRECTION APPLIED", 0, 0, d60))

        out.extend(record)
        counters.written += 1

    return Result(bytes(out), report, counters)


def main(argv: list[str]) -> int:
    base = Path(argv[1]) if len(argv) > 1 else Path("data")
    result = run((base / "BMFMOD.dat").read_bytes(),
                 (base / "TRANIN.dat").read_bytes())
    (base / "MODDUP.dat").write_bytes(result.modules)
    text = "".join(line + "\n" for line in result.report)
    (base / "DUPCHK.rpt").write_text(text, encoding="latin-1")
    for line in result.counters.display_lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
