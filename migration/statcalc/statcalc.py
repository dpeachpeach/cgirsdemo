"""Python port of STATCALC (pipeline step 030) — statute date computation.

Behavioral port of src/STATCALC.cbl and the COBOL shim src/DATCNV.cbl.
Legacy behavior is reproduced as-is, defects included; see
reports/PORT-STATCALC-<date>.md for the catalogue.

Reads  data/MODDUP.dat  (150-byte fixed BMF module records)
Writes data/MODSTAT.dat, data/STATCALC.rpt
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Callable

REC_LEN = 150
RPT_LEN = 120

# BMFMOD.cpy field offsets (zero-relative, [start, end))
F_EIN = (0, 9)
F_MFT = (9, 11)
F_TXPD = (11, 17)
F_FRZ = (58, 66)
F_ASED = (66, 70)
F_RSED = (70, 74)
F_CSED = (74, 78)
F_ASSD = (78, 85)
F_DEP = (85, 92)
F_CRD = (92, 99)
F_W8 = (123, 131)

DTM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def unpack_comp3(raw: bytes, scale: int = 0) -> Decimal:
    """Decode a COMP-3 (packed decimal) field. Sign nibble D is negative."""
    digits = "".join(f"{b:02x}" for b in raw)
    sign = digits[-1]
    value = Decimal(digits[:-1] or "0")
    if scale:
        value = value.scaleb(-scale)
    if sign in ("b", "d"):
        value = -value
    return value


def pack_comp3(value: Decimal, digits: int, scale: int = 0, signed: bool = True) -> bytes:
    """Encode a Decimal into COMP-3. Truncates toward zero like a COBOL MOVE."""
    scaled = int((abs(value) * (10**scale)).to_integral_value(rounding="ROUND_DOWN"))
    body = str(scaled % (10**digits)).rjust(digits, "0")
    sign = "f" if not signed else ("d" if value < 0 else "c")
    nibbles = body + sign
    if len(nibbles) % 2:
        nibbles = "0" + nibbles
    return bytes.fromhex(nibbles)


def move_to_numeric(text: str, digits: int) -> int:
    """MOVE of an alphanumeric item into PIC 9(n).

    GnuCOBOL keeps the low-order digits and treats a non-digit byte by its
    low nibble, which is how spaces (0x20) become zero.
    """
    kept = text[-digits:].rjust(digits, "0")
    return int("".join(str(ord(c) & 0x0F) for c in kept))


class Trace:
    """Branch-hit recorder used for coverage measurement."""

    def __init__(self) -> None:
        self.hits: dict[str, int] = {}

    def __call__(self, branch: str) -> None:
        self.hits[branch] = self.hits.get(branch, 0) + 1


class DatcnvParm:
    """DC-PARM as STATCALC declares it: WORKING-STORAGE, so it survives calls.

    DATCNV leaves DCP-JUL untouched when it sets RC 8, and STATCALC never
    inspects RC, so a rejected conversion silently reuses the previous
    record's Julian date.
    """

    def __init__(self) -> None:
        self.func = " "
        self.greg = 0
        self.jul = 0
        self.rc = " "

    def call(self, hit: Callable[[str], None]) -> None:
        self.rc = "0"
        if self.func == "J":
            hit("D1")
            self._to_julian(hit)
        elif self.func == "G":
            hit("D2")
            self._to_gregorian(hit)
        else:
            hit("D3")
            self.rc = "8"

    def _to_julian(self, hit: Callable[[str], None]) -> None:
        ky = self.greg // 10000
        km = (self.greg // 100) % 100
        kd = self.greg % 100
        if km < 1 or km > 12 or kd < 1 or kd > 31:
            hit("D4")
            self.rc = "8"
            return
        hit("D5")
        kl = _leap(ky, hit)
        ka = 0
        for k1 in range(1, km):
            ka += DTM[k1 - 1]
            if k1 == 2:
                hit("D10")  # leap adjustment inside the accumulation loop
                ka += kl
        ka += kd
        self.jul = ky * 1000 + ka

    def _to_gregorian(self, hit: Callable[[str], None]) -> None:
        ky = self.jul // 1000
        ka = self.jul - ky * 1000
        kl = _leap(ky, hit)
        if ka < 1 or ka > 365 + kl:
            hit("D6")
            self.rc = "8"
            return
        km = 1
        while km <= 12:
            kr = DTM[km - 1]
            if km == 2:
                hit("D9")
                kr += kl
            if ka <= kr:
                hit("D7")
                break
            ka -= kr
            km += 1
        else:
            hit("D8")  # loop exhausted; 2000-BLD builds a date with KM = 13
        self.greg = ky * 10000 + km * 100 + ka


def _leap(ky: int, hit: Callable[[str], None]) -> int:
    if ky % 4 != 0:
        hit("D11")
        return 0
    if ky % 100 != 0:
        hit("D12")
        return 1
    if ky % 400 != 0:
        hit("D13")
        return 0
    hit("D14")
    return 1


class Record:
    """A BMF module record, mutable in place like the COBOL FD area."""

    def __init__(self, raw: bytes) -> None:
        self.raw = bytearray(raw)

    def text(self, field: tuple[int, int]) -> str:
        return self.raw[field[0] : field[1]].decode("latin-1")

    def num(self, field: tuple[int, int]) -> int:
        return int(self.text(field))

    def packed(self, field: tuple[int, int], scale: int = 0) -> Decimal:
        return unpack_comp3(bytes(self.raw[field[0] : field[1]]), scale)

    def set_packed(self, field: tuple[int, int], value: int) -> None:
        width = field[1] - field[0]
        digits = width * 2 - 1
        self.raw[field[0] : field[1]] = pack_comp3(
            Decimal(value), digits, scale=0, signed=False
        )

    @property
    def ein(self) -> str:
        return self.text(F_EIN)

    @property
    def mft(self) -> int:
        return self.num(F_MFT)

    @property
    def txpd(self) -> str:
        return self.text(F_TXPD)


class Statcalc:
    """STATCALC's PROCEDURE DIVISION, WORKING-STORAGE included."""

    def __init__(self, trace: Trace | None = None) -> None:
        self.trace = trace or Trace()
        self.r1 = 0  # records read
        self.r2 = 0  # records written
        self.r6 = 0  # "6YR" counter — never incremented by any path
        self.r7 = 0  # suspend/special counter
        # WORKING-STORAGE report line fields persist across records
        self.sr_cod = "    "
        self.sr_txt = " " * 34
        self.sr_ein = "0" * 9
        self.sr_mft = "00"
        self.sr_txpd = "0" * 6
        self.sr_ased = 0
        self.sr_csed = 0
        self.report: list[str] = []
        self.w7as = 0
        self.w7rs = 0
        self.w7cs = 0
        self.w7rd = 0
        self.sy = 0
        self.sm = 0
        self.sdy = 0
        self.parm = DatcnvParm()

    def run(self, modin: bytes) -> tuple[bytes, str]:
        out = bytearray()
        offset = 0
        while True:
            if offset >= len(modin):
                self.trace("S1")  # READ ... AT END
                break
            self.trace("S2")  # READ ... NOT AT END
            rec = Record(modin[offset : offset + REC_LEN])
            offset += REC_LEN
            self.r1 += 1
            self.calc(rec)
            out += rec.raw
            self.r2 += 1
        return bytes(out), "".join(self.report)

    # 2100-CALC
    def calc(self, rec: Record) -> None:
        scc = move_to_numeric(rec.text(F_W8)[0:2], 2)
        self.rdd(rec)
        self.ased()
        self.spcl(rec, scc)
        self.rsed(rec)
        self.csed(rec)
        rec.set_packed(F_ASED, self.w7as)
        rec.set_packed(F_RSED, self.w7rs)
        rec.set_packed(F_CSED, self.w7cs)

    # 2200-RDD — return due date, then Julian
    def rdd(self, rec: Record) -> None:
        hit = self.trace
        self.sy = int(rec.txpd[0:4])
        self.sm = int(rec.txpd[4:6])
        if rec.mft == 1:
            hit("S3")
            self.sm = (self.sm + 1) % 100  # ADD into PIC 9(2) truncates
            if self.sm > 12:
                hit("S4")
                self.sm -= 12
                self.sy = (self.sy + 1) % 10000
            else:
                hit("S5")
            self.sdy = 28
        elif rec.mft == 2:
            hit("S6")
            self.sm = (self.sm + 4) % 100  # ADD into PIC 9(2) truncates
            if self.sm > 12:
                hit("S7")
                self.sm -= 12
                self.sy = (self.sy + 1) % 10000
            else:
                hit("S8")
            self.sdy = 15
        else:
            hit("S9")
            self.sy = (self.sy + 1) % 10000
            self.sm = 1
            self.sdy = 31
        sdt = self.sy * 10000 + self.sm * 100 + self.sdy
        self.parm.func = "J"
        self.parm.greg = sdt % 10**8  # MOVE SDT TO DCP-GREG, both PIC 9(8)
        self.parm.call(hit)
        self.w7rd = self.parm.jul

    # 2300-ASED
    def ased(self) -> None:
        w7yr = self.sy + 3
        self.w7as = w7yr * 1000 + self.w7rd % 1000

    # 2350-SPCL
    def spcl(self, rec: Record, scc: int) -> None:
        hit = self.trace
        if scc == 7:
            hit("S11")
            self.w7as = 9999365
            self.r7 += 1
            self.sr_cod = "S302"
            self.sr_txt = "FRAUD - ASED NOT LIMITED".ljust(34)
            self.rpt(rec)
        elif scc == 12:
            hit("S12")
            w7yr = self.sy + 3
            self.w7as = w7yr * 1000 + 105
            self.r7 += 1
            self.sr_cod = "S303"
            self.sr_txt = "FORM 872 CONSENT - ASED EXTENDED".ljust(34)
            self.rpt(rec)
        else:
            hit("S13")

    # 2400-RSED
    def rsed(self, rec: Record) -> None:
        hit = self.trace
        w7yr = self.sy + 3
        self.w7rs = w7yr * 1000 + self.w7rd % 1000
        if rec.packed(F_DEP, 2) > 0:
            hit("S14")
            w7yr = self.sy + 2
            if w7yr * 1000 > self.w7rs:
                hit("S16")
                self.w7rs = w7yr * 1000 + self.w7rd % 1000
            else:
                hit("S17")
        else:
            hit("S15")

    # 2500-CSED
    def csed(self, rec: Record) -> None:
        hit = self.trace
        w7yr = self.sy + 10
        self.w7cs = w7yr * 1000 + self.w7rd % 1000
        frz = rec.text(F_FRZ)
        if frz[1] == "V" or frz[6] == "Z":
            hit("S18")
            if frz[1] == "V":
                hit("S18V")
            if frz[6] == "Z":
                hit("S18Z")
            self.w7cs += 183
            if self.w7cs % 1000 > 365:
                hit("S20")
                self.w7cs += 1000
                self.w7cs -= 365
            else:
                hit("S21")
            self.r7 += 1
            self.sr_cod = "S304"
            self.sr_txt = "CSED SUSPENDED - BANKRUPTCY".ljust(34)
            self.rpt(rec)
        else:
            hit("S19")

    # 8000-RPT
    def rpt(self, rec: Record) -> None:
        self.sr_ein = rec.ein
        self.sr_mft = rec.text(F_MFT)
        self.sr_txpd = rec.txpd
        self.sr_ased = self.w7as
        self.sr_csed = self.w7cs
        line = (
            "STATCALC"
            + "  "
            + self.sr_ein
            + " "
            + self.sr_mft
            + " "
            + self.sr_txpd
            + "  "
            + self.sr_cod
            + "  "
            + self.sr_txt
            + "  "
            + f"{self.sr_ased % 10**7:07d}"
            + " "
            + f"{self.sr_csed % 10**7:07d}"
            + " " * 30
        )
        # SRPT is 118 bytes; WRITE FROM into the 120-byte record space-pads.
        self.report.append(line.ljust(RPT_LEN).rstrip(" ") + "\n")

    def displays(self) -> str:
        return (
            f"STATCALC READ   {self.r1:06d}\n"
            f"STATCALC WRITTEN{self.r2:06d}\n"
            f"STATCALC 6YR    {self.r6:06d}\n"
            f"STATCALC SUSPEND{self.r7:06d}\n"
        )


def run_files(data_dir: Path) -> Statcalc:
    modin = (data_dir / "MODDUP.dat").read_bytes()
    job = Statcalc()
    modstat, report = job.run(modin)
    (data_dir / "MODSTAT.dat").write_bytes(modstat)
    (data_dir / "STATCALC.rpt").write_text(report)
    return job


def main(argv: list[str]) -> int:
    data_dir = Path(argv[1]) if len(argv) > 1 else Path("data")
    job = run_files(data_dir)
    sys.stdout.write(job.displays())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
