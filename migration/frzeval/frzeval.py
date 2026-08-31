"""Python port of FRZEVAL (step 070) — freeze condition evaluation.

Characterization port of src/FRZEVAL.cbl. Behavior is defined by what the
COBOL program does, not by IRM 21.5.6: reads data/MODEST.dat, writes
data/MODFRZ.dat and data/FRZEVAL.rpt.

FRZEVAL calls no subprograms, so the HLASM shims (src/NAMCTL.cbl,
src/DATCNV.cbl, src/PENACC.cbl) do not participate in this step.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

RECORD_LENGTH = 150

# BMFMOD.cpy displacements, zero-relative.
OFF_EIN = 0
OFF_MFT = 9
OFF_TXPD = 11
OFF_FRZ = 58
LEN_FRZ = 8
OFF_FRZ_A = OFF_FRZ + 0
OFF_FRZ_V = OFF_FRZ + 1
OFF_FRZ_L = OFF_FRZ + 2
OFF_FRZ_R = OFF_FRZ + 3
OFF_FRZ_S = OFF_FRZ + 4
OFF_FRZ_X = OFF_FRZ + 5
OFF_FRZ_Z = OFF_FRZ + 6
OFF_FRZ_O = OFF_FRZ + 7
OFF_ASSD = 78
OFF_DEP = 85
OFF_CRD = 92
OFF_PFTD = 99
OFF_PFTF = 105
OFF_PFTP = 111

# S9(11)V99 COMP-3 -> 13 digits -> 7 bytes; S9(09)V99 -> 11 digits -> 6 bytes.
LEN_AMT13 = 7
LEN_AMT11 = 6

WBAL_INT_DIGITS = 11          # WBAL is PIC S9(11)V99 COMP-3
ZR_BAL_INT_DIGITS = 9         # ZR-BAL is PIC ZZZZZZZZ9.99-
CENT = Decimal("0.01")


def unpack_decimal(raw: bytes, scale: int) -> Decimal:
    """Decode a packed-decimal (COMP-3) field into a Decimal."""
    nibbles = []
    for byte in raw:
        nibbles.append(byte >> 4)
        nibbles.append(byte & 0x0F)
    sign_nibble = nibbles.pop()
    digits = "".join(str(n) for n in nibbles)
    value = Decimal(digits).scaleb(-scale)
    if sign_nibble == 0x0D:
        value = -value
    return value


def pack_decimal(value: Decimal, digits: int, scale: int, signed: bool = True) -> bytes:
    """Encode a Decimal as packed decimal with the given digit count."""
    scaled = int(value.scaleb(scale).to_integral_value(rounding="ROUND_DOWN"))
    negative = scaled < 0
    text = str(abs(scaled)).zfill(digits)[-digits:]
    if digits % 2 == 0:
        text = "0" + text
    sign_nibble = 0x0D if (signed and negative) else 0x0C
    out = bytearray()
    for i in range(0, len(text) - 1, 2):
        out.append((int(text[i]) << 4) | int(text[i + 1]))
    out.append((int(text[-1]) << 4) | sign_nibble)
    return bytes(out)


def truncate_int_digits(value: Decimal, int_digits: int) -> Decimal:
    """Reproduce COBOL high-order truncation into a field of int_digits digits."""
    limit = Decimal(10) ** int_digits
    sign = -1 if value < 0 else 1
    magnitude = abs(value) % limit
    return sign * magnitude


def edit_zr_bal(value: Decimal) -> str:
    """Format a value as PIC ZZZZZZZZ9.99- (13 characters)."""
    truncated = truncate_int_digits(value, ZR_BAL_INT_DIGITS)
    magnitude = abs(truncated).quantize(CENT)
    whole = int(magnitude)
    cents = int((magnitude - whole) * 100)
    sign = "-" if truncated < 0 else " "
    return f"{whole:9d}.{cents:02d}{sign}"


@dataclass
class Counters:
    read: int = 0
    written: int = 0
    refund_suppressed: int = 0
    offset_suppressed: int = 0


@dataclass
class ReportLine:
    ein: str
    mft: str
    txpd: str
    code: str
    text: str
    frz: str
    balance: Decimal

    def render(self) -> str:
        line = (
            "FRZEVAL"
            + "  "
            + self.ein
            + " "
            + self.mft
            + " "
            + self.txpd
            + "  "
            + f"{self.code:<4}"
            + "  "
            + f"{self.text:<30}"
            + "  "
            + f"{self.frz:<8}"
            + "  "
            + edit_zr_bal(self.balance)
            + " " * 20
        )
        return line.rstrip()


def evaluate_record(record: bytes, counters: Counters) -> tuple[bytes, ReportLine | None]:
    """Perform 2100-FRZ for one module record."""
    out = bytearray(record)
    frz = record[OFF_FRZ:OFF_FRZ + LEN_FRZ].decode("latin-1")

    wbal = truncate_int_digits(
        unpack_decimal(record[OFF_ASSD:OFF_ASSD + LEN_AMT13], 2)
        + unpack_decimal(record[OFF_PFTD:OFF_PFTD + LEN_AMT11], 2)
        + unpack_decimal(record[OFF_PFTF:OFF_PFTF + LEN_AMT11], 2)
        + unpack_decimal(record[OFF_PFTP:OFF_PFTP + LEN_AMT11], 2)
        - unpack_decimal(record[OFF_DEP:OFF_DEP + LEN_AMT13], 2)
        - unpack_decimal(record[OFF_CRD:OFF_CRD + LEN_AMT13], 2),
        WBAL_INT_DIGITS,
    )

    refund_ok = True
    offset_ok = True
    freeze_count = 0

    if record[OFF_FRZ_A:OFF_FRZ_A + 1] == b"A":
        refund_ok = False
        freeze_count += 1
    if record[OFF_FRZ_L:OFF_FRZ_L + 1] == b"L":
        refund_ok = False
        offset_ok = False
        freeze_count += 1
    if record[OFF_FRZ_V:OFF_FRZ_V + 1] == b"V":
        offset_ok = False
        freeze_count += 1
    if record[OFF_FRZ_S:OFF_FRZ_S + 1] == b"S":
        refund_ok = False
        freeze_count += 1
    if record[OFF_FRZ_Z:OFF_FRZ_Z + 1] == b"Z":
        refund_ok = False
        offset_ok = False
        freeze_count += 1

    if not refund_ok:
        counters.refund_suppressed += 1
        out[OFF_FRZ_R:OFF_FRZ_R + 1] = b"R"
    if not offset_ok:
        counters.offset_suppressed += 1
        out[OFF_FRZ_O:OFF_FRZ_O + 1] = b"O"

    line = None
    if freeze_count > 0:
        if not refund_ok and not offset_ok:
            text = "REFUND AND OFFSET SUPPRESSED"
        elif not refund_ok:
            text = "REFUND SUPPRESSED"
        else:
            text = "OFFSET SUPPRESSED"
        # ZR-FRZ is moved after BMF-FRZ-R / BMF-FRZ-O are updated, so the
        # report shows the codes this run just set.
        line = ReportLine(
            ein=out[OFF_EIN:OFF_EIN + 9].decode("latin-1"),
            mft=out[OFF_MFT:OFF_MFT + 2].decode("latin-1"),
            txpd=out[OFF_TXPD:OFF_TXPD + 6].decode("latin-1"),
            code="Z701",
            text=text,
            frz=out[OFF_FRZ:OFF_FRZ + LEN_FRZ].decode("latin-1"),
            balance=wbal,
        )
    return bytes(out), line


def run(records: list[bytes]) -> tuple[list[bytes], list[str], Counters]:
    counters = Counters()
    out_records: list[bytes] = []
    report: list[str] = []
    for record in records:
        counters.read += 1
        new_record, line = evaluate_record(record, counters)
        out_records.append(new_record)
        counters.written += 1
        if line is not None:
            report.append(line.render())
    return out_records, report, counters


def read_records(path: Path) -> list[bytes]:
    raw = path.read_bytes()
    return [raw[i:i + RECORD_LENGTH] for i in range(0, len(raw), RECORD_LENGTH)]


def main(argv: list[str]) -> int:
    base = Path(argv[1]) if len(argv) > 1 else Path(".")
    records = read_records(base / "data" / "MODEST.dat")
    out_records, report, counters = run(records)
    (base / "data" / "MODFRZ.dat").write_bytes(b"".join(out_records))
    text = "".join(line + "\n" for line in report)
    (base / "data" / "FRZEVAL.rpt").write_text(text, encoding="latin-1")
    print(f"FRZEVAL READ    {counters.read:06d}")
    print(f"FRZEVAL WRITTEN {counters.written:06d}")
    print(f"FRZEVAL RFND SUP{counters.refund_suppressed:06d}")
    print(f"FRZEVAL OFST SUP{counters.offset_suppressed:06d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
