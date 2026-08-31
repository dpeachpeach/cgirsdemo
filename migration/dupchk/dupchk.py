"""Python port of the COBOL program DUPCHK (pipeline step 020).

Behaviour is characterized against `src/DUPCHK.cbl` as compiled by GnuCOBOL
3.1.2, not against IRM 21.7.9. Where the COBOL has a defect the port
reproduces it; see reports/PORT-DUPCHK-*.md for the proposed fixes.

Reads  data/BMFMOD.dat, data/TRANIN.dat
Writes data/MODDUP.dat, data/DUPCHK.rpt
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

MOD_LRECL = 150
TRN_LRECL = 80

BMF_KEY = slice(0, 17)
BMF_EIN = slice(0, 9)
BMF_MFT = slice(9, 11)
BMF_TXPD = slice(11, 17)
BMF_FRZ_A = slice(58, 59)
BMF_ASED = slice(66, 70)
BMF_TCCNT = slice(131, 134)

TRN_EIN = slice(0, 9)
TRN_MFT = slice(9, 11)
TRN_TXPD = slice(11, 17)
TRN_TC = slice(17, 20)
TRN_DT = slice(20, 27)

HIGH_VALUES = b"\xff" * 17

RPT_LRECL = 120


def comp3_to_int(raw: bytes) -> int:
    """Unpacks an unsigned packed-decimal (COMP-3) field."""
    digits = raw.hex()
    return int(digits[:-1] or "0")


def int_to_comp3(value: int, digits: int) -> bytes:
    """Packs `digits` digits unsigned, sign nibble F, as COBOL PIC 9(n) COMP-3."""
    text = f"{value % (10 ** digits):0{digits}d}"
    if digits % 2 == 0:
        text = "0" + text
    return bytes.fromhex(text + "F")


def display_to_int(raw: bytes) -> int:
    return int(raw.decode("ascii"))


def int_to_display(value: int, width: int) -> bytes:
    """MOVE into PIC 9(width) DISPLAY: truncate high-order digits, zero-fill."""
    return f"{value % (10 ** width):0{width}d}".encode("ascii")


@dataclass
class Counters:
    """The four PIC 9(6) tallies DUPCHK displays at end of job."""

    read: int = 0
    written: int = 0
    a_freeze: int = 0
    ased_corrected: int = 0

    def display_lines(self) -> list[str]:
        return [
            f"DUPCHK  READ    {self.read % 1000000:06d}",
            f"DUPCHK  WRITTEN {self.written % 1000000:06d}",
            f"DUPCHK  A FREEZE{self.a_freeze % 1000000:06d}",
            f"DUPCHK  ASED COR{self.ased_corrected % 1000000:06d}",
        ]


@dataclass
class Result:
    mod_out: bytes
    report: str
    counters: Counters


def _report_line(ein: bytes, mft: bytes, txpd: bytes, code: str, text: str,
                 dr_a: int, dr_b: int, dr_c: int) -> str:
    record = (
        b"DUPCHK"
        + b"  "
        + ein
        + b" "
        + mft
        + b" "
        + txpd
        + b"  "
        + f"{code:<4.4}".encode("ascii")
        + b"  "
        + f"{text:<38.38}".encode("ascii")
        + b"  "
        + int_to_display(dr_a, 3)
        + b" "
        + int_to_display(dr_b, 3)
        + b" "
        + int_to_display(dr_c, 7)
        + b" " * 30
    )
    assert len(record) == RPT_LRECL
    # LINE SEQUENTIAL strips trailing blanks and appends a newline.
    return record.decode("ascii").rstrip(" ") + "\n"


def process(mod_in: bytes, trn_in: bytes) -> Result:
    """Runs the DUPCHK match/merge over in-memory copies of both input files."""
    mods = [mod_in[i:i + MOD_LRECL] for i in range(0, len(mod_in), MOD_LRECL)]
    trns = [trn_in[i:i + TRN_LRECL] for i in range(0, len(trn_in), TRN_LRECL)]

    counters = Counters()
    out_records: list[bytes] = []
    report: list[str] = []

    trn_pos = 0
    teof = False
    trn_rec = b""
    tkey = b""

    def read_trn() -> None:
        nonlocal trn_pos, teof, trn_rec, tkey
        if trn_pos >= len(trns):
            teof = True
            tkey = HIGH_VALUES
            return
        trn_rec = trns[trn_pos]
        trn_pos += 1
        tkey = trn_rec[TRN_EIN] + trn_rec[TRN_MFT] + trn_rec[TRN_TXPD]

    read_trn()  # 1000-INIT

    for record in mods:
        counters.read += 1
        rec = bytearray(record)
        mkey = bytes(rec[BMF_KEY])
        c50 = c76 = c77 = c60 = 0
        d60 = d76 = 0
        dupsw = False

        # 2200-SKIP: transactions below the module key are consumed silently.
        while not teof and tkey < mkey:
            read_trn()

        # 2300-GATHER
        while not teof and tkey == mkey:
            tc = display_to_int(trn_rec[TRN_TC])
            if tc == 150:
                c50 = (c50 + 1) % 1000
            elif tc == 976:
                c76 = (c76 + 1) % 1000
                d76 = display_to_int(trn_rec[TRN_DT])
            elif tc == 977:
                c77 = (c77 + 1) % 1000
            elif tc == 560:
                c60 = (c60 + 1) % 1000
                d60 = display_to_int(trn_rec[TRN_DT])
            tccnt = display_to_int(bytes(rec[BMF_TCCNT]))
            rec[BMF_TCCNT] = int_to_display(tccnt + 1, 3)
            read_trn()

        # 2400-EVAL
        if c50 > 0 and (c76 > 0 or c77 > 0):
            dupsw = True
        if c50 > 1:
            dupsw = True
        if c76 > 0 and c60 > 0:
            dupsw = False
        if dupsw:
            rec[BMF_FRZ_A] = b"A"
            counters.a_freeze += 1
            report.append(_report_line(
                bytes(rec[BMF_EIN]), bytes(rec[BMF_MFT]), bytes(rec[BMF_TXPD]),
                "D201", "DUP FILING - A FREEZE SET", c76, c77, d76))

        # 2500-ASED
        if c60 > 0:
            w_ased = comp3_to_int(bytes(rec[BMF_ASED]))
            if d60 > w_ased:
                rec[BMF_ASED] = int_to_comp3(d60, 7)
                counters.ased_corrected += 1
                report.append(_report_line(
                    bytes(rec[BMF_EIN]), bytes(rec[BMF_MFT]),
                    bytes(rec[BMF_TXPD]),
                    "D202", "TC 560 ASED CORRECTION APPLIED", 0, 0, d60))

        out_records.append(bytes(rec))
        counters.written += 1

    return Result(b"".join(out_records), "".join(report), counters)


def run(mod_in_path: str | Path = "data/BMFMOD.dat",
        trn_in_path: str | Path = "data/TRANIN.dat",
        mod_out_path: str | Path = "data/MODDUP.dat",
        rpt_path: str | Path = "data/DUPCHK.rpt") -> Counters:
    result = process(Path(mod_in_path).read_bytes(),
                     Path(trn_in_path).read_bytes())
    Path(mod_out_path).write_bytes(result.mod_out)
    Path(rpt_path).write_text(result.report, encoding="ascii")
    return result.counters


def main() -> int:
    counters = run()
    for line in counters.display_lines():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
