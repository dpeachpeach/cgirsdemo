"""Python port of src/STATCALC.cbl (pipeline step 030).

Reads MODDUP.dat, writes MODSTAT.dat and STATCALC.rpt.  Behaviour is
characterized against the GnuCOBOL build of the legacy program; defects in
the COBOL are reproduced here deliberately and are asserted in
migration/statcalc/tests/.

The called subprogram DATCNV is ported from the COBOL shim src/DATCNV.cbl
(the HLASM under src/asm/ does not execute).
"""

from decimal import Decimal
from pathlib import Path

RECORD_LEN = 150
REPORT_LEN = 120

# copybooks/BMFMOD.cpy offsets (0-relative, byte length)
F_EIN = (0, 9)
F_MFT = (9, 2)
F_TXPD = (11, 6)
F_FRZ = (58, 8)
F_ASED = (66, 4)      # PIC 9(7) COMP-3
F_RSED = (70, 4)      # PIC 9(7) COMP-3
F_CSED = (74, 4)      # PIC 9(7) COMP-3
F_ASSD = (78, 7)      # PIC S9(11)V99 COMP-3
F_DEP = (85, 7)       # PIC S9(11)V99 COMP-3
F_W8 = (123, 8)

DTM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def unpack_comp3(raw: bytes, scale: int = 0) -> Decimal:
    """Decode a packed-decimal (COMP-3) field.  D in the sign nibble is
    negative, everything else is positive, as on the mainframe."""
    nibbles = "".join(f"{b >> 4:x}{b & 0x0F:x}" for b in raw)
    digits, sign = nibbles[:-1], nibbles[-1]
    value = Decimal(int(digits))
    if scale:
        value = value.scaleb(-scale)
    return -value if sign == "d" else value


def pack_comp3(value: Decimal, digits: int, scale: int = 0, signed: bool = False) -> bytes:
    """Encode into a COMP-3 field of `digits` digits.  Unsigned targets carry
    an F sign nibble, signed ones C/D, matching what BLDFIX and the COBOL
    runtime write."""
    scaled = int((value.scaleb(scale)).to_integral_value())
    negative = scaled < 0
    scaled = abs(scaled) % (10 ** digits)
    text = str(scaled).rjust(digits, "0")
    if not signed:
        sign = "f"
    else:
        sign = "d" if negative else "c"
    nibbles = text + sign
    return bytes(int(nibbles[i : i + 2], 16) for i in range(0, len(nibbles), 2))


def _field(rec: bytes, spec) -> bytes:
    off, length = spec
    return rec[off : off + length]


class Datcnv:
    """COBOL shim src/DATCNV.cbl.  The parm area is WORKING-STORAGE in the
    caller, so DCP-JUL keeps its previous value when a call fails."""

    def __init__(self, trace=None):
        self.greg = 0
        self.jul = 0
        self.rc = "0"
        self.trace = trace if trace is not None else set()

    def _hit(self, branch: str) -> None:
        self.trace.add(branch)

    def leap_adjust(self, year: int) -> int:
        """3000-LEAP."""
        if year % 4 == 0:
            self._hit("B26")
            if year % 100 == 0:
                self._hit("B28")
                if year % 400 == 0:
                    self._hit("B30")
                    return 1
                self._hit("B31")
                return 0
            self._hit("B29")
            return 1
        self._hit("B27")
        return 0

    def call(self, func: str, greg: int = 0, jul: int = 0) -> None:
        """0000-ENT."""
        self.rc = "0"
        if func == "J":
            self._hit("B21")
            self.to_julian(greg)
        elif func == "G":
            self._hit("B22")
            self.to_gregorian(jul)
        else:
            self._hit("B23")
            self.rc = "8"

    def to_julian(self, greg: int) -> None:
        self.greg = greg % 10 ** 8
        text = str(self.greg).rjust(8, "0")
        ky, km, kd = int(text[0:4]), int(text[4:6]), int(text[6:8])
        if km < 1 or km > 12 or kd < 1 or kd > 31:
            self._hit("B24")
            self.rc = "8"
            return
        self._hit("B25")
        kl = self.leap_adjust(ky)
        ka = 0
        if km == 1:
            self._hit("B34")
        for k1 in range(1, km):
            ka += DTM[k1 - 1]
            if k1 == 2:
                self._hit("B32")
                ka += kl
            else:
                self._hit("B33")
        ka += kd
        self.jul = (ky * 1000 + ka) % 10 ** 7

    def to_gregorian(self, jul: int) -> None:
        """2000-TOGRG.  Unreachable from STATCALC, which only ever asks for J."""
        self.jul = jul % 10 ** 7
        ky = self.jul // 1000
        ka = self.jul - ky * 1000
        kl = self.leap_adjust(ky)
        if ka < 1 or ka > 365 + kl:
            self._hit("B35")
            self.rc = "8"
            return
        self._hit("B36")
        km = 1
        while km <= 12:
            kr = DTM[km - 1]
            if km == 2:
                self._hit("B37")
                kr += kl
            if ka <= kr:
                self._hit("B38")
                break
            ka -= kr
            km += 1
        else:
            self._hit("B39")
        self.greg = (ky * 10000 + km * 100 + ka) % 10 ** 8


class Statcalc:
    """One instance == one execution of the program: the counters, the report
    work area and the DATCNV parm area all live across records, exactly as the
    COBOL WORKING-STORAGE does."""

    def __init__(self, trace=None):
        self.r1 = self.r2 = self.r6 = self.r7 = 0
        self.trace = trace if trace is not None else set()
        self.datcnv = Datcnv(self.trace)
        self.report = []
        self.w7as = 0
        self.w7rs = 0
        self.w7cs = 0
        self.sr_cod = "    "
        self.sr_txt = " " * 34
        self.w7rd = 0

    def _hit(self, branch: str) -> None:
        self.trace.add(branch)

    # 0000-MAIN / 2000-PROC
    def run(self, records):
        out = []
        for rec in records:
            self._hit("B02")
            self.r1 += 1
            out.append(self.calc(rec))
            self.r2 += 1
        self._hit("B01")
        return out

    # 2100-CALC
    def calc(self, rec: bytes) -> bytes:
        rec = rec.ljust(RECORD_LEN)[:RECORD_LEN]
        w8 = _field(rec, F_W8).decode("latin-1")
        scc = self._numeric_move(w8[0:2])
        sy = self.rdd(rec)
        self.ased(sy, rec, scc)
        self.rsed(sy, rec)
        self.csed(sy, rec)
        out = bytearray(rec)
        out[F_ASED[0] : F_ASED[0] + F_ASED[1]] = pack_comp3(Decimal(self.w7as), 7)
        out[F_RSED[0] : F_RSED[0] + F_RSED[1]] = pack_comp3(Decimal(self.w7rs), 7)
        out[F_CSED[0] : F_CSED[0] + F_CSED[1]] = pack_comp3(Decimal(self.w7cs), 7)
        return bytes(out)

    @staticmethod
    def _numeric_move(text: str) -> int:
        """MOVE BMF-W8(1:2) TO SCC — alphanumeric to numeric-display.  Spaces
        are dropped and the remaining digits right-align; any other non-digit
        byte makes the whole move store zero."""
        digits = text.replace(" ", "")
        if not digits.isdigit():
            return 0
        return int(digits) if digits else 0

    # 2200-RDD
    def rdd(self, rec: bytes) -> int:
        txpd = _field(rec, F_TXPD).decode("latin-1")
        sy = int(txpd[0:4])
        sm = int(txpd[4:6])
        mft = int(_field(rec, F_MFT).decode("latin-1"))
        if mft == 1:
            self._hit("B03")
            sm += 1
            if sm > 12:
                self._hit("B04")
                sm -= 12
                sy += 1
            else:
                self._hit("B05")
            sdy = 28
        elif mft == 2:
            self._hit("B06")
            sm += 4
            if sm > 12:
                self._hit("B07")
                sm -= 12
                sy += 1
            else:
                self._hit("B08")
            sdy = 15
        else:
            self._hit("B09")
            sy += 1
            sm = 1
            sdy = 31
        sdt = (sy * 10000 + sm * 100 + sdy) % 10 ** 8
        self.datcnv.call("J", greg=sdt)
        self.w7rd = self.datcnv.jul
        return sy

    # 2300-ASED / 2350-SPCL
    def ased(self, sy: int, rec: bytes, scc: int) -> None:
        w7yr = sy + 3
        self.w7as = (w7yr * 1000 + self.w7rd % 1000) % 10 ** 7
        if scc == 7:
            self._hit("B10")
            self.w7as = 9999365
            self.r7 += 1
            self.sr_cod = "S302"
            self.sr_txt = "FRAUD - ASED NOT LIMITED".ljust(34)
            self.write_report(rec)
        elif scc == 12:
            self._hit("B11")
            w7yr = sy + 3
            self.w7as = (w7yr * 1000 + 105) % 10 ** 7
            self.r7 += 1
            self.sr_cod = "S303"
            self.sr_txt = "FORM 872 CONSENT - ASED EXTENDED".ljust(34)
            self.write_report(rec)
        else:
            self._hit("B12")

    # 2400-RSED
    def rsed(self, sy: int, rec: bytes) -> None:
        w7yr = sy + 3
        self.w7rs = (w7yr * 1000 + self.w7rd % 1000) % 10 ** 7
        dep = unpack_comp3(_field(rec, F_DEP), scale=2)
        if dep > 0:
            self._hit("B13")
            w7yr = sy + 2
            if w7yr * 1000 > self.w7rs:
                self._hit("B15")
                self.w7rs = (w7yr * 1000 + self.w7rd % 1000) % 10 ** 7
            else:
                self._hit("B16")
        else:
            self._hit("B14")

    # 2500-CSED
    def csed(self, sy: int, rec: bytes) -> None:
        w7yr = sy + 10
        self.w7cs = (w7yr * 1000 + self.w7rd % 1000) % 10 ** 7
        frz = _field(rec, F_FRZ).decode("latin-1")
        if frz[1] == "V" or frz[6] == "Z":
            self._hit("B17")
            self.w7cs = (self.w7cs + 183) % 10 ** 7
            if self.w7cs % 1000 > 365:
                self._hit("B19")
                self.w7cs = (self.w7cs + 1000 - 365) % 10 ** 7
            else:
                self._hit("B20")
            self.r7 += 1
            self.sr_cod = "S304"
            self.sr_txt = "CSED SUSPENDED - BANKRUPTCY".ljust(34)
            self.write_report(rec)
        else:
            self._hit("B18")

    # 8000-RPT
    def write_report(self, rec: bytes) -> None:
        line = (
            "STATCALC"
            + "  "
            + _field(rec, F_EIN).decode("latin-1")
            + " "
            + _field(rec, F_MFT).decode("latin-1")
            + " "
            + _field(rec, F_TXPD).decode("latin-1")
            + "  "
            + self.sr_cod
            + "  "
            + self.sr_txt
            + "  "
            + str(self.w7as).rjust(7, "0")
            + " "
            + str(self.w7cs).rjust(7, "0")
            + " " * 30
        )
        self.report.append(line[:REPORT_LEN])

    def totals(self):
        return {"read": self.r1, "written": self.r2, "6yr": self.r6, "suspend": self.r7}


def split_records(blob: bytes):
    return [blob[i : i + RECORD_LEN] for i in range(0, len(blob), RECORD_LEN)]


def run_file(in_path, out_path=None, rpt_path=None):
    blob = Path(in_path).read_bytes()
    prog = Statcalc()
    out = prog.run(split_records(blob))
    if out_path:
        Path(out_path).write_bytes(b"".join(out))
    lines = [line.rstrip() for line in prog.report]
    if rpt_path:
        Path(rpt_path).write_text("\n".join(lines) + ("\n" if lines else ""))
    return out, lines, prog


def main():
    out, lines, prog = run_file("data/MODDUP.dat", "data/MODSTAT.dat", "data/STATCALC.rpt")
    t = prog.totals()
    print(f"STATCALC READ   {t['read']:06d}")
    print(f"STATCALC WRITTEN{t['written']:06d}")
    print(f"STATCALC 6YR    {t['6yr']:06d}")
    print(f"STATCALC SUSPEND{t['suspend']:06d}")


if __name__ == "__main__":
    main()
