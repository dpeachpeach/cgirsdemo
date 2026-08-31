"""FRZEVAL - freeze condition evaluation, step 070 of the BMF nightly cycle.

Python port of ``src/FRZEVAL.cbl``. Behaviour is characterized against the
COBOL program, defects included; see ``tests/`` and the port report.

Reads ``data/MODEST.dat``, writes ``data/MODFRZ.dat`` and ``data/FRZEVAL.rpt``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

RECORD_LENGTH = 150

MODIN_PATH = "data/MODEST.dat"
MODOT_PATH = "data/MODFRZ.dat"
FZRPT_PATH = "data/FRZEVAL.rpt"


def unpack_comp3(raw: bytes, scale: int, signed: bool) -> Decimal:
    """Decode a COMP-3 (packed decimal) field into a Decimal."""
    digits = raw.hex().upper()
    sign_nibble = digits[-1]
    value = Decimal(digits[:-1] or "0")
    if signed and sign_nibble == "D":
        value = -value
    return value.scaleb(-scale)


def pack_comp3(value: Decimal, digits: int, scale: int, signed: bool) -> bytes:
    """Encode a Decimal into a COMP-3 field of ``digits`` digits."""
    scaled = int(value.scaleb(scale).to_integral_value())
    negative = scaled < 0
    body = str(abs(scaled)).rjust(digits, "0")[-digits:]
    if signed:
        sign_nibble = "D" if negative else "C"
    else:
        sign_nibble = "F"
    nibbles = body + sign_nibble
    if len(nibbles) % 2:
        nibbles = "0" + nibbles
    return bytes.fromhex(nibbles)


def truncate_to_picture(value: Decimal, int_digits: int, scale: int) -> Decimal:
    """Store ``value`` into a PIC S9(int_digits)V9(scale) field.

    COBOL truncates both the low-order digits beyond the field's scale and,
    with no ON SIZE ERROR clause, the high-order digits that do not fit. The
    sign of the original value is retained.
    """
    scaled = int(value.scaleb(scale).to_integral_value())
    negative = scaled < 0
    scaled = abs(scaled) % (10 ** (int_digits + scale))
    result = Decimal(scaled).scaleb(-scale)
    return -result if negative else result


def edit_zzzzzzzz9_99_minus(value: Decimal) -> str:
    """Format a value under PIC ZZZZZZZZ9.99- (13 character positions)."""
    stored = truncate_to_picture(value, 9, 2)
    negative = stored < 0
    cents = abs(int(stored.scaleb(2).to_integral_value()))
    whole, frac = divmod(cents, 100)
    body = f"{whole:d}.{frac:02d}".rjust(12)
    return body + ("-" if negative else " ")


# Field offsets from copybooks/BMFMOD.cpy.
_OFF_EIN = (0, 9)
_OFF_MFT = (9, 11)
_OFF_TXPD = (11, 17)
_OFF_FRZ = (58, 66)
_OFF_ASSD = (78, 85)
_OFF_DEP = (85, 92)
_OFF_CRD = (92, 99)
_OFF_PFTD = (99, 105)
_OFF_PFTF = (105, 111)
_OFF_PFTP = (111, 117)


@dataclass
class BmfModRecord:
    """The 150-byte BMF tax module record, as far as FRZEVAL touches it."""

    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != RECORD_LENGTH:
            raise ValueError(f"BMF module record must be {RECORD_LENGTH} bytes")

    def _text(self, span: tuple[int, int]) -> str:
        return self.raw[span[0]:span[1]].decode("latin-1")

    def _packed(self, span: tuple[int, int], scale: int, signed: bool) -> Decimal:
        return unpack_comp3(self.raw[span[0]:span[1]], scale, signed)

    @property
    def ein(self) -> str:
        return self._text(_OFF_EIN)

    @property
    def mft(self) -> str:
        return self._text(_OFF_MFT)

    @property
    def txpd(self) -> str:
        return self._text(_OFF_TXPD)

    @property
    def frz(self) -> str:
        return self._text(_OFF_FRZ)

    # BMF-FRZ is a group of eight single-character freeze positions.
    @property
    def frz_a(self) -> str:
        return self.frz[0]

    @property
    def frz_v(self) -> str:
        return self.frz[1]

    @property
    def frz_l(self) -> str:
        return self.frz[2]

    @property
    def frz_r(self) -> str:
        return self.frz[3]

    @property
    def frz_s(self) -> str:
        return self.frz[4]

    @property
    def frz_x(self) -> str:
        return self.frz[5]

    @property
    def frz_z(self) -> str:
        return self.frz[6]

    @property
    def frz_o(self) -> str:
        return self.frz[7]

    @property
    def assd(self) -> Decimal:
        return self._packed(_OFF_ASSD, 2, True)

    @property
    def dep(self) -> Decimal:
        return self._packed(_OFF_DEP, 2, True)

    @property
    def crd(self) -> Decimal:
        return self._packed(_OFF_CRD, 2, True)

    @property
    def pftd(self) -> Decimal:
        return self._packed(_OFF_PFTD, 2, True)

    @property
    def pftf(self) -> Decimal:
        return self._packed(_OFF_PFTF, 2, True)

    @property
    def pftp(self) -> Decimal:
        return self._packed(_OFF_PFTP, 2, True)

    def with_freeze_position(self, index: int, char: str) -> "BmfModRecord":
        frz = list(self.frz)
        frz[index] = char
        start, end = _OFF_FRZ
        return BmfModRecord(self.raw[:start] + "".join(frz).encode("latin-1") + self.raw[end:])


@dataclass
class FrzEvalResult:
    """What 2100-FRZ produced for one module record."""

    record: BmfModRecord
    report_line: str | None
    refund_suppressed: bool
    offset_suppressed: bool
    freeze_count: int
    balance: Decimal


def format_report_line(record: BmfModRecord, refund_suppressed: bool,
                       offset_suppressed: bool, balance: Decimal) -> str:
    """Build the ZRPT line. Trailing FILLER is stripped by LINE SEQUENTIAL."""
    if refund_suppressed and offset_suppressed:
        text = "REFUND AND OFFSET SUPPRESSED"
    elif refund_suppressed:
        text = "REFUND SUPPRESSED"
    else:
        text = "OFFSET SUPPRESSED"
    line = (
        "FRZEVAL"
        + "  "
        + record.ein
        + " "
        + record.mft
        + " "
        + record.txpd
        + "  "
        + "Z701"
        + "  "
        + text.ljust(30)
        + "  "
        + record.frz
        + "  "
        + edit_zzzzzzzz9_99_minus(balance)
    )
    return line.rstrip(" ")


def evaluate_freeze(record: BmfModRecord) -> FrzEvalResult:
    """2100-FRZ: derive refund/offset suppression from the freeze positions."""
    refund_ok = True
    offset_ok = True
    freeze_count = 0

    # BMF-INT is deliberately absent from this sum; the COBOL does not include it.
    balance = truncate_to_picture(
        record.assd + record.pftd + record.pftf + record.pftp - record.dep - record.crd,
        11,
        2,
    )

    if record.frz_a == "A":
        refund_ok = False
        freeze_count += 1
    if record.frz_l == "L":
        refund_ok = False
        offset_ok = False
        freeze_count += 1
    if record.frz_v == "V":
        offset_ok = False
        freeze_count += 1
    if record.frz_s == "S":
        refund_ok = False
        freeze_count += 1
    if record.frz_z == "Z":
        refund_ok = False
        offset_ok = False
        freeze_count += 1

    if not refund_ok:
        record = record.with_freeze_position(3, "R")
    if not offset_ok:
        record = record.with_freeze_position(7, "O")

    report_line = None
    if freeze_count > 0:
        report_line = format_report_line(record, not refund_ok, not offset_ok, balance)

    return FrzEvalResult(
        record=record,
        report_line=report_line,
        refund_suppressed=not refund_ok,
        offset_suppressed=not offset_ok,
        freeze_count=freeze_count,
        balance=balance,
    )


@dataclass
class FrzEvalRun:
    """Everything one execution of the step produced."""

    out_records: list[bytes]
    report_lines: list[str]
    read_count: int
    written_count: int
    refund_suppressed_count: int
    offset_suppressed_count: int

    @property
    def out_data(self) -> bytes:
        return b"".join(self.out_records)

    @property
    def report_text(self) -> str:
        return "".join(line + "\n" for line in self.report_lines)

    @property
    def stdout_text(self) -> str:
        return (
            f"FRZEVAL READ    {self.read_count:06d}\n"
            f"FRZEVAL WRITTEN {self.written_count:06d}\n"
            f"FRZEVAL RFND SUP{self.refund_suppressed_count:06d}\n"
            f"FRZEVAL OFST SUP{self.offset_suppressed_count:06d}\n"
        )


def run(modin_data: bytes) -> FrzEvalRun:
    """0000-MAIN: drive 2100-FRZ over every record of the input file."""
    out_records: list[bytes] = []
    report_lines: list[str] = []
    read_count = written_count = refund_count = offset_count = 0

    for offset in range(0, len(modin_data), RECORD_LENGTH):
        record = BmfModRecord(modin_data[offset:offset + RECORD_LENGTH])
        read_count += 1
        result = evaluate_freeze(record)
        if result.refund_suppressed:
            refund_count += 1
        if result.offset_suppressed:
            offset_count += 1
        if result.report_line is not None:
            report_lines.append(result.report_line)
        out_records.append(result.record.raw)
        written_count += 1

    return FrzEvalRun(
        out_records=out_records,
        report_lines=report_lines,
        read_count=read_count,
        written_count=written_count,
        refund_suppressed_count=refund_count,
        offset_suppressed_count=offset_count,
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    base = Path(argv[0]) if argv else Path.cwd()
    result = run((base / MODIN_PATH).read_bytes())
    (base / MODOT_PATH).write_bytes(result.out_data)
    (base / FZRPT_PATH).write_text(result.report_text)
    sys.stdout.write(result.stdout_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
