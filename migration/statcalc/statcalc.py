"""Python port of src/STATCALC.cbl (BMF step 030) and the DATCNV shim it calls.

Behaviour is characterized against GnuCOBOL 3.1.2 output, not against IRM 25.6.1.
Known legacy defects are reproduced deliberately; see tests/ for the assertions
that pin them and reports/PORT-STATCALC-*.md for the proposed fixes.

The port targets src/DATCNV.cbl (the COBOL shim). The HLASM in src/asm/ does not
execute in this corpus and was not used as a reference for behaviour.
"""

from decimal import Decimal
from pathlib import Path

REC_LEN = 150
RPT_LEN = 120

# BMFMOD.cpy field offsets, zero-based, into the 150-byte module record.
OFF_EIN = (0, 9)
OFF_MFT = (9, 11)
OFF_TXPD = (11, 17)
OFF_FRZ = (58, 66)
OFF_ASED = (66, 70)
OFF_RSED = (70, 74)
OFF_CSED = (74, 78)
OFF_DEP = (85, 92)
OFF_W8 = (123, 131)

# DATCNV DTAB: days per month, February without the leap day.
DTM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def unpack_decimal(raw: bytes, scale: int = 0) -> Decimal:
    """Read a COMP-3 (packed decimal) field the way GnuCOBOL wrote it."""
    nibbles = "".join(f"{b >> 4:x}{b & 0x0F:x}" for b in raw)
    digits, sign = nibbles[:-1], nibbles[-1]
    value = Decimal(digits)
    if sign in ("b", "d"):
        value = -value
    if scale:
        value = value.scaleb(-scale)
    return value


def pack_unsigned(value: int, digits: int) -> bytes:
    """Write PIC 9(digits) COMP-3: digits plus an 0xF sign nibble, zero-filled."""
    body = str(int(value) % (10 ** digits)).zfill(digits)
    nibbles = body + "f"
    if len(nibbles) % 2:
        nibbles = "0" + nibbles
    return bytes(
        int(nibbles[i], 16) << 4 | int(nibbles[i + 1], 16)
        for i in range(0, len(nibbles), 2)
    )


def _field(rec: bytes, off: tuple) -> bytes:
    return rec[off[0]:off[1]]


def _text(rec: bytes, off: tuple) -> str:
    return _field(rec, off).decode("latin-1")


class Datcnv:
    """COBOL shim src/DATCNV.cbl. The parm area lives in STATCALC's
    WORKING-STORAGE, so DCP-JUL keeps its previous value when a call fails."""

    def __init__(self, trace=None):
        self.jul = 0
        self.greg = 0
        self.rc = "0"
        self.rsv = " " * 7
        self._trace = trace if trace is not None else set()

    def call(self, func: str, greg: int = 0) -> None:
        self.rc = "0"
        if func == "J":
            self._trace.add("D01")
            self._to_julian(greg)
        elif func == "G":
            self._trace.add("D02")
            self._to_gregorian()
        else:
            self._trace.add("D03")
            self.rc = "8"

    def _leap(self, year: int) -> int:
        if year % 4 == 0:
            self._trace.add("D09")
            if year % 100 == 0:
                self._trace.add("D11")
                if year % 400 == 0:
                    self._trace.add("D13")
                    return 1
                self._trace.add("D14")
                return 0
            self._trace.add("D12")
            return 1
        self._trace.add("D10")
        return 0

    def _to_julian(self, greg: int) -> None:
        self.greg = greg
        text = str(greg).zfill(8)
        ky, km, kd = int(text[0:4]), int(text[4:6]), int(text[6:8])
        if km < 1 or km > 12 or kd < 1 or kd > 31:
            self._trace.add("D04")
            self.rc = "8"
            return
        self._trace.add("D05")
        kl = self._leap(ky)
        ka = 0
        k1 = 1
        while k1 < km:
            self._trace.add("D06")
            ka += DTM[k1 - 1]
            if k1 == 2:
                self._trace.add("D07")
                ka += kl
            k1 += 1
        if km == 1:
            self._trace.add("D08")
        ka += kd
        self.jul = ky * 1000 + ka

    def _to_gregorian(self) -> None:
        # Unreachable from STATCALC (it only ever issues function "J"), kept for
        # fidelity with the shim.
        ky = self.jul // 1000
        ka = self.jul - ky * 1000
        kl = self._leap(ky)
        if ka < 1 or ka > 365 + kl:
            self.rc = "8"
            return
        km = 1
        while km <= 12:
            kr = DTM[km - 1] + (kl if km == 2 else 0)
            if ka <= kr:
                break
            ka -= kr
            km += 1
        self.greg = ky * 10000 + km * 100 + ka


class Statcalc:
    """One run of step 030: MODDUP.dat in, MODSTAT.dat plus STATCALC.rpt out."""

    def __init__(self):
        self.branches = set()
        self.datcnv = Datcnv(self.branches)
        self.report_lines = []
        # WORKING-STORAGE counters and work fields persist across records.
        self.r1 = 0
        self.r2 = 0
        self.r6 = 0
        self.r7 = 0
        self.w7rd = 0
        self.w7as = 0
        self.w7rs = 0
        self.w7cs = 0
        self.w7yr = 0
        self.sy = 0
        self.sm = 0
        self.sdy = 0
        self.scc = 0
        # SRPT report fields are WORKING-STORAGE too: 8000-RPT never refreshes
        # SR-CSED before the S302/S303 writes, so a stale value is emitted.
        self.sr_ein = 0
        self.sr_mft = 0
        self.sr_txpd = 0
        self.sr_cod = "    "
        self.sr_txt = " " * 34
        self.sr_ased = 0
        self.sr_csed = 0

    # ---- 0000-MAIN / 2000-PROC -------------------------------------------
    def run(self, moddup: bytes) -> tuple:
        out = bytearray()
        for offset in range(0, len(moddup) - REC_LEN + 1, REC_LEN):
            self.branches.add("B02")
            rec = bytearray(moddup[offset:offset + REC_LEN])
            self.r1 += 1
            self.calc(rec)
            out += bytes(rec)
            self.r2 += 1
        self.branches.add("B01")
        report = "".join(line.rstrip() + "\n" for line in self.report_lines)
        return bytes(out), report, self.counters()

    def counters(self) -> dict:
        return {"READ": self.r1, "WRITTEN": self.r2, "6YR": self.r6, "SUSPEND": self.r7}

    def counters_text(self) -> str:
        c = self.counters()
        return (
            f"STATCALC READ   {c['READ']:06d}\n"
            f"STATCALC WRITTEN{c['WRITTEN']:06d}\n"
            f"STATCALC 6YR    {c['6YR']:06d}\n"
            f"STATCALC SUSPEND{c['SUSPEND']:06d}\n"
        )

    # ---- 2100-CALC --------------------------------------------------------
    def calc(self, rec: bytearray) -> None:
        w8 = _text(rec, OFF_W8)
        self.scc = int(w8[0:2]) if w8[0:2].isdigit() else -1
        self.rdd(rec)
        self.ased(rec)
        self.rsed(rec)
        self.csed(rec)
        rec[OFF_ASED[0]:OFF_ASED[1]] = pack_unsigned(self.w7as, 7)
        rec[OFF_RSED[0]:OFF_RSED[1]] = pack_unsigned(self.w7rs, 7)
        rec[OFF_CSED[0]:OFF_CSED[1]] = pack_unsigned(self.w7cs, 7)

    # ---- 2200-RDD ---------------------------------------------------------
    def rdd(self, rec: bytearray) -> None:
        txpd = _text(rec, OFF_TXPD)
        self.sy = int(txpd[0:4])
        self.sm = int(txpd[4:6])
        mft = int(_text(rec, OFF_MFT))
        if mft == 1:
            self.branches.add("B03")
            self.sm += 1
            if self.sm > 12:
                self.branches.add("B04")
                self.sm -= 12
                self.sy += 1
            else:
                self.branches.add("B05")
            self.sdy = 28
        elif mft == 2:
            self.branches.add("B06")
            self.sm += 4
            if self.sm > 12:
                self.branches.add("B07")
                self.sm -= 12
                self.sy += 1
            else:
                self.branches.add("B08")
            self.sdy = 15
        else:
            self.branches.add("B09")
            self.sy += 1
            self.sm = 1
            self.sdy = 31
        sdt = self.sy * 10000 + self.sm * 100 + self.sdy
        self.datcnv.call("J", sdt)
        self.w7rd = self.datcnv.jul

    # ---- 2300-ASED / 2350-SPCL -------------------------------------------
    def ased(self, rec: bytearray) -> None:
        self.w7yr = self.sy + 3
        self.w7as = self.w7yr * 1000 + self.w7rd % 1000
        if self.scc == 7:
            self.branches.add("B10")
            self.w7as = 9999365
            self.r7 += 1
            self.sr_cod = "S302"
            self.sr_txt = "FRAUD - ASED NOT LIMITED"
            self.report(rec)
        elif self.scc == 12:
            self.branches.add("B11")
            self.w7yr = self.sy + 3
            w8 = _text(rec, OFF_W8)
            self.datcnv.rsv = w8[3:8] + self.datcnv.rsv[5:]
            self.w7as = self.w7yr * 1000 + 105
            self.r7 += 1
            self.sr_cod = "S303"
            self.sr_txt = "FORM 872 CONSENT - ASED EXTENDED"
            self.report(rec)
        else:
            self.branches.add("B12")

    # ---- 2400-RSED --------------------------------------------------------
    def rsed(self, rec: bytearray) -> None:
        self.w7yr = self.sy + 3
        self.w7rs = self.w7yr * 1000 + self.w7rd % 1000
        if unpack_decimal(_field(rec, OFF_DEP), 2) > 0:
            self.branches.add("B13")
            self.w7yr = self.sy + 2
            if self.w7yr * 1000 > self.w7rs:
                # Dead branch: (SY+2)*1000 can never exceed (SY+3)*1000 + day.
                self.branches.add("B15")
                self.w7rs = self.w7yr * 1000 + self.w7rd % 1000
            else:
                self.branches.add("B16")
        else:
            self.branches.add("B14")

    # ---- 2500-CSED --------------------------------------------------------
    def csed(self, rec: bytearray) -> None:
        frz = _text(rec, OFF_FRZ)
        self.w7yr = self.sy + 10
        self.w7cs = self.w7yr * 1000 + self.w7rd % 1000
        if frz[1] == "V" or frz[6] == "Z":
            self.branches.add("B17" if frz[1] == "V" else "B18")
            self.w7cs += 183
            if self.w7cs % 1000 > 365:
                self.branches.add("B20")
                self.w7cs += 1000
                self.w7cs -= 365
            else:
                self.branches.add("B21")
            self.r7 += 1
            self.sr_cod = "S304"
            self.sr_txt = "CSED SUSPENDED - BANKRUPTCY"
            self.report(rec)
        else:
            self.branches.add("B19")

    # ---- 8000-RPT ---------------------------------------------------------
    def report(self, rec: bytearray) -> None:
        self.sr_ein = int(_text(rec, OFF_EIN))
        self.sr_mft = int(_text(rec, OFF_MFT))
        self.sr_txpd = int(_text(rec, OFF_TXPD))
        self.sr_ased = self.w7as
        self.sr_csed = self.w7cs
        line = (
            "STATCALC"
            + "  "
            + f"{self.sr_ein:09d}"
            + " "
            + f"{self.sr_mft:02d}"
            + " "
            + f"{self.sr_txpd:06d}"
            + "  "
            + f"{self.sr_cod:<4}"
            + "  "
            + f"{self.sr_txt:<34}"[:34]
            + "  "
            + f"{self.sr_ased:07d}"
            + " "
            + f"{self.sr_csed:07d}"
        )
        self.report_lines.append(f"{line:<{RPT_LEN}}")


def main(base: Path = Path(".")) -> None:
    engine = Statcalc()
    moddup = (base / "data" / "MODDUP.dat").read_bytes()
    modstat, report, _ = engine.run(moddup)
    (base / "data" / "MODSTAT.dat").write_bytes(modstat)
    (base / "data" / "STATCALC.rpt").write_text(report)
    print(engine.counters_text(), end="")


if __name__ == "__main__":
    main()
