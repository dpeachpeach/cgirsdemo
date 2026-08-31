"""PENCALC - failure to file / failure to pay penalty calculation (step 050).

Python port of src/PENCALC.cbl plus the DATCNV COBOL shim (src/DATCNV.cbl) it
calls.  The HLASM routine src/asm/DATCNV.asm does not execute in this corpus;
the shim is the ported specification.

Behavior is a characterization of the compiled COBOL, including its defects.
See reports/PORT-PENCALC-<date>.md for the catalogue.
"""

from __future__ import annotations

import datetime
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

MOD_LRECL = 150
TRN_LRECL = 80
RPT_LRECL = 120

HIGH_VALUES = b"\xff" * 17

# Enumerated conditional paths of src/PENCALC.cbl and the DATCNV shim it CALLs.
# Every hit() site below records one of these; Result.branches is the set that a
# given input exercised.
BRANCHES = {
    "B01": "0000-MAIN: PERFORM UNTIL MEOF exits on module end-of-file",
    "B02": "2000-DRIVE: a module record was read",
    "B03": "2100-PEN: transaction key below module key, skip it",
    "B04": "2100-PEN: skip loop exits because TKEY not < MKEY",
    "B05": "2100-PEN: skip loop exits on transaction end-of-file",
    "B06": "2100-PEN: transaction key equals module key",
    "B07": "2100-PEN: match loop exits because TKEY not = MKEY",
    "B08": "2100-PEN: matched transaction is TC 150, take its date",
    "B09": "2100-PEN: matched transaction is not TC 150",
    "B10": "2100-PEN: match loop exits on transaction end-of-file",
    "B11": "2100-PEN: WUPD < ZERO, floored to zero",
    "B12": "2100-PEN: WUPD not negative",
    "B13": "2100-PEN: WMOL > 0 AND WUPD > 0, penalties assessed",
    "B14": "2100-PEN: no penalty assessed",
    "B15": "2200-MONTHS: D150 = ZERO, WMOL zeroed and paragraph exits",
    "B16": "2200-MONTHS: D150 present",
    "B17": "2200-MONTHS: due month rolls into the next year",
    "B18": "2200-MONTHS: due month stays in the same year",
    "B19": "2200-MONTHS: WDLD < 1 (filed on time), WMOL zeroed",
    "B20": "2200-MONTHS: WDLD >= 1, WMOL = WDLD / 30 + 1",
    "B21": "2300-FTF: FTF above the 25% cap, capped",
    "B22": "2300-FTF: FTF at or below the 25% cap",
    "B23": "2400-FTP: FTP above the 25% cap, capped",
    "B24": "2400-FTP: FTP at or below the 25% cap",
    "B25": "2500-OFFSET: FTP > ZERO, FTF reduced by FTP",
    "B26": "2500-OFFSET: FTP not positive, no offset",
    "B27": "2500-OFFSET: offset drove FTF negative, floored to zero",
    "B28": "2500-OFFSET: offset left FTF non-negative",
    "B29": "2600-MIN: WDLD > 60, minimum penalty considered",
    "B30": "2600-MIN: WDLD <= 60, paragraph does nothing",
    "B31": "2600-MIN: WUPD < WMIN, minimum capped by the balance",
    "B32": "2600-MIN: WUPD >= WMIN",
    "B33": "2600-MIN: FTF < WMIN, minimum applied and P502 written",
    "B34": "2600-MIN: FTF >= WMIN, minimum not applied",
    "B35": "8100-RDTRN: transaction file at end, TKEY set to HIGH-VALUES",
    "B36": "8100-RDTRN: transaction record read",
    "B37": "DATCNV 0000-MAIN: function J (Gregorian to Julian)",
    "B38": "DATCNV 0000-MAIN: function G (Julian to Gregorian)",
    "B39": "DATCNV 0000-MAIN: unknown function, RC 8",
    "B40": "DATCNV 2000-GREG: Julian day out of range, RC 8",
    "B41": "DATCNV 2000-GREG: Julian day in range",
    "B42": "DATCNV 2000-GREG: month found, loop left early",
    "B43": "DATCNV 2000-GREG: February examined, leap day added",
    "B44": "DATCNV 3000-LEAP: year divisible by 4",
    "B45": "DATCNV 3000-LEAP: year not divisible by 4",
    "B46": "DATCNV 3000-LEAP: year divisible by 100",
    "B47": "DATCNV 3000-LEAP: year divisible by 400",
    "B48": "DATCNV 2000-GREG: month loop ran past December",
}

# ---------------------------------------------------------------------------
# COBOL primitives
# ---------------------------------------------------------------------------


def unpack_comp3(raw: bytes, scale: int) -> Decimal:
    """Unpack a COMP-3 (packed decimal) field. Low nibble of last byte is sign."""
    digits = ""
    for byte in raw[:-1]:
        digits += str(byte >> 4) + str(byte & 0x0F)
    last = raw[-1]
    digits += str(last >> 4)
    sign = -1 if (last & 0x0F) in (0x0B, 0x0D) else 1
    value = Decimal(digits or "0").scaleb(-scale)
    return value * sign


def pack_comp3(value: Decimal, digits: int, scale: int, signed: bool = True) -> bytes:
    """Pack into COMP-3, truncating high-order digits and low-order positions."""
    scaled = truncate(value, scale).scaleb(scale).to_integral_value()
    negative = scaled < 0
    text = str(abs(int(scaled))).rjust(digits, "0")[-digits:]
    if len(text) % 2 == 0:
        text = "0" + text
    if signed:
        sign_nibble = "D" if negative else "C"
    else:
        sign_nibble = "F"
    nibbles = text + sign_nibble
    return bytes(
        int(nibbles[i], 16) << 4 | int(nibbles[i + 1], 16)
        for i in range(0, len(nibbles), 2)
    )


def truncate(value: Decimal, scale: int) -> Decimal:
    """Store into a PIC with `scale` decimal places: truncate toward zero."""
    quantum = Decimal(1).scaleb(-scale)
    return value.quantize(quantum, rounding="ROUND_DOWN")


def store(value: Decimal, digits: int, scale: int) -> Decimal:
    """Store into PIC S9(digits-scale)V9(scale): truncate low-order positions,
    then drop high-order digits that do not fit."""
    scaled = int(truncate(value, scale).scaleb(scale))
    sign = -1 if scaled < 0 else 1
    return Decimal(sign * (abs(scaled) % 10**digits)).scaleb(-scale)


def binary_truncate(value: int, digits: int) -> int:
    """Store into a COMP field with binary-truncate: keep `digits` decimal digits."""
    limit = 10**digits
    sign = -1 if value < 0 else 1
    return sign * (abs(value) % limit)


def integer_of_date(yyyymmdd: int) -> int:
    """FUNCTION INTEGER-OF-DATE: days since 1600-12-31, 0 for an invalid argument."""
    year, month, day = yyyymmdd // 10000, (yyyymmdd // 100) % 100, yyyymmdd % 100
    if not (1601 <= year <= 9999 and 1 <= month <= 12 and 1 <= day <= 31):
        return 0
    try:
        target = datetime.date(year, month, day)
    except ValueError:
        return 0
    return target.toordinal() - datetime.date(1600, 12, 31).toordinal()


# ---------------------------------------------------------------------------
# DATCNV shim (src/DATCNV.cbl), Julian -> Gregorian direction
# ---------------------------------------------------------------------------

DTM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _leap(year: int, hits: set | None = None) -> int:
    """3000-LEAP: 1 when `year` is a leap year, else 0."""
    def hit(branch: str) -> None:
        if hits is not None:
            hits.add(branch)

    if year % 4:
        hit("B45")
        return 0
    hit("B44")
    if year % 100:
        return 1
    hit("B46")
    if year % 400 == 0:
        hit("B47")
        return 1
    return 0


def datcnv(
    func: str, greg: int = 0, jul: int = 0, hits: set | None = None
) -> tuple[int, int, str]:
    """DATCNV entry point. Returns (greg, jul, return code)."""
    if func == "J":
        if hits is not None:
            hits.add("B37")
        return _to_julian(greg, jul, hits)
    if func == "G":
        if hits is not None:
            hits.add("B38")
        return _to_gregorian(greg, jul, hits)
    if hits is not None:
        hits.add("B39")
    return greg, jul, "8"


def _to_julian(greg: int, jul: int, hits: set | None = None) -> tuple[int, int, str]:
    ky, km, kd = greg // 10000, (greg // 100) % 100, greg % 100
    if km < 1 or km > 12 or kd < 1 or kd > 31:
        return greg, jul, "8"
    kl = _leap(ky, hits)
    ka = 0
    for k1 in range(1, km):
        ka += DTM[k1 - 1]
        if k1 == 2:
            ka += kl
    ka += kd
    return greg, binary_truncate(ky * 1000 + ka, 7), "0"


def _to_gregorian(greg: int, jul: int, hits: set | None = None) -> tuple[int, int, str]:
    def hit(branch: str) -> None:
        if hits is not None:
            hits.add(branch)

    ky = jul // 1000
    ka = jul - ky * 1000
    kl = _leap(ky, hits)
    if ka < 1 or ka > 365 + kl:
        hit("B40")
        return greg, jul, "8"
    hit("B41")
    km = 1
    while km <= 12:
        kr = DTM[km - 1] + (kl if km == 2 else 0)
        if km == 2:
            hit("B43")
        if ka <= kr:
            hit("B42")
            break
        ka -= kr
        km += 1
    else:
        # PERFORM UNTIL KM > 12 exhausted without reaching 2000-BLD via GO TO;
        # control still falls into 2000-BLD. Unreachable for a valid KA.
        hit("B48")
    return ky * 10000 + km * 100 + ka, jul, "0"


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


class ModRecord:
    """BMF-MOD-REC as copybooks/BMFMOD.cpy lays it out."""

    def __init__(self, raw: bytes):
        self.raw = bytearray(raw)

    def _text(self, start: int, length: int) -> str:
        return self.raw[start : start + length].decode("latin-1")

    @property
    def key(self) -> bytes:
        return bytes(self.raw[0:17])

    @property
    def ein(self) -> str:
        return self._text(0, 9)

    @property
    def mft(self) -> str:
        return self._text(9, 2)

    @property
    def txpd(self) -> str:
        return self._text(11, 6)

    @property
    def assd(self) -> Decimal:
        return unpack_comp3(bytes(self.raw[78:85]), 2)

    @property
    def dep(self) -> Decimal:
        return unpack_comp3(bytes(self.raw[85:92]), 2)

    @property
    def crd(self) -> Decimal:
        return unpack_comp3(bytes(self.raw[92:99]), 2)

    @property
    def pftf(self) -> Decimal:
        return unpack_comp3(bytes(self.raw[105:111]), 2)

    @pftf.setter
    def pftf(self, value: Decimal) -> None:
        self.raw[105:111] = pack_comp3(value, 11, 2)

    @property
    def pftp(self) -> Decimal:
        return unpack_comp3(bytes(self.raw[111:117]), 2)

    @pftp.setter
    def pftp(self, value: Decimal) -> None:
        self.raw[111:117] = pack_comp3(value, 11, 2)


class TrnRecord:
    """TRN-REC as copybooks/TRANREC.cpy lays it out."""

    def __init__(self, raw: bytes):
        self.raw = raw

    @property
    def key(self) -> bytes:
        return self.raw[0:17]

    @property
    def tc(self) -> int:
        return int(self.raw[17:20])

    @property
    def dt(self) -> str:
        return self.raw[20:27].decode("latin-1")


# ---------------------------------------------------------------------------
# Report line
# ---------------------------------------------------------------------------


def _zz9(value: int) -> str:
    """PIC ZZ9 - three positions, leading zero suppression."""
    text = str(binary_truncate(value, 3)).rjust(3)
    return text[-3:]


def _money_edit(value: Decimal) -> str:
    """PIC ZZZZZZ9.99 - ten positions, leading zero suppression, no sign."""
    truncated = truncate(abs(value), 2)
    whole = int(truncated)
    cents = int((truncated - whole) * 100)
    return f"{whole % 10000000:7d}.{cents:02d}"


def report_line(
    ein: str, mft: str, txpd: str, code: str, text: str, months: int,
    ftf: Decimal, ftp: Decimal,
) -> str:
    """PRPT, written into PIC X(120) and then trailing-space trimmed by
    LINE SEQUENTIAL output."""
    line = (
        "PENCALC" + "  " + ein + " " + mft + " " + txpd + "  " + code[:4].ljust(4)
        + "  " + text[:24].ljust(24) + "  " + _zz9(months) + " "
        + _money_edit(ftf) + " " + _money_edit(ftp) + " " * 30
    )
    return line.ljust(RPT_LRECL)[:RPT_LRECL].rstrip()


# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------

MINIMUM_PENALTY = Decimal("485.00")


@dataclass
class Counters:
    read: int = 0
    written: int = 0
    ftf: int = 0
    minimum: int = 0


@dataclass
class Result:
    mod_out: bytes
    report: str
    counters: Counters
    branches: set = field(default_factory=set)


class _Pencalc:
    def __init__(self, mod_in: bytes, trn_in: bytes):
        self.mod_records = [
            mod_in[i : i + MOD_LRECL] for i in range(0, len(mod_in), MOD_LRECL)
        ]
        self.trn_records = [
            trn_in[i : i + TRN_LRECL] for i in range(0, len(trn_in), TRN_LRECL)
        ]
        self.trn_pos = 0
        self.teof = False
        self.tkey = b"\x00" * 17
        self.trn: TrnRecord | None = None
        self.out = bytearray()
        self.lines: list[str] = []
        self.counters = Counters()
        self.branches: set[str] = set()
        # 2200-MONTHS leaves WDLD set from the previous record when it takes the
        # D150 = ZERO exit; WORKING-STORAGE is not re-initialised per record.
        self.wdld = 0
        self.wmol = 0

    def hit(self, branch: str) -> None:
        self.branches.add(branch)

    # 8100-RDTRN
    def read_trn(self) -> None:
        if self.trn_pos >= len(self.trn_records):
            self.hit("B35")
            self.teof = True
            self.tkey = HIGH_VALUES
            return
        self.hit("B36")
        self.trn = TrnRecord(self.trn_records[self.trn_pos])
        self.trn_pos += 1
        self.tkey = self.trn.key

    def run(self) -> Result:
        self.read_trn()
        for raw in self.mod_records:  # 2000-DRIVE
            self.hit("B02")
            self.counters.read += 1
            mod = ModRecord(raw)
            self.pen(mod)
            self.out += mod.raw
            self.counters.written += 1
        self.hit("B01")
        report = "".join(line + "\n" for line in self.lines)
        return Result(bytes(self.out), report, self.counters, self.branches)

    # 2100-PEN
    def pen(self, mod: ModRecord) -> None:
        mkey = mod.key
        d150 = "0000000"
        wf51 = Decimal(0)
        wf52 = Decimal(0)
        self.wmol = 0

        while True:  # PERFORM UNTIL TEOF = "Y" OR TKEY NOT < MKEY
            if self.teof:
                self.hit("B05")
                break
            if self.tkey >= mkey:
                self.hit("B04")
                break
            self.hit("B03")
            self.read_trn()

        while True:  # PERFORM UNTIL TEOF = "Y" OR TKEY NOT = MKEY
            if self.teof:
                self.hit("B10")
                break
            if self.tkey != mkey:
                self.hit("B07")
                break
            self.hit("B06")
            assert self.trn is not None
            if self.trn.tc == 150:
                self.hit("B08")
                d150 = self.trn.dt
            else:
                self.hit("B09")
            self.read_trn()

        wupd = store(mod.assd - mod.dep - mod.crd, 13, 2)
        if wupd < 0:
            self.hit("B11")
            wupd = Decimal(0)
        else:
            self.hit("B12")

        self.months(mod, d150)

        if self.wmol > 0 and wupd > 0:
            self.hit("B13")
            wf51 = self.ftf(wupd)
            wf52 = self.ftp(wupd)
            wf51 = self.offset(wf51, wf52)
            wf51 = self.minimum(mod, wupd, wf51, wf52)
            mod.pftf = wf51
            mod.pftp = wf52
            self.counters.ftf += 1
            self.lines.append(
                report_line(
                    mod.ein, mod.mft, mod.txpd, "P501", "FTF/FTP ASSESSED",
                    self.wmol, wf51, wf52,
                )
            )
        else:
            self.hit("B14")

    # 2200-MONTHS
    def months(self, mod: ModRecord, d150: str) -> None:
        if int(d150) == 0:
            self.hit("B15")
            self.wmol = 0
            return
        self.hit("B16")
        vy = int(mod.txpd[0:4])
        vm = int(mod.txpd[4:6]) + 1
        if vm > 12:
            self.hit("B17")
            vm -= 12
            vy += 1
        else:
            self.hit("B18")
        gr = vy * 10000 + vm * 100 + 15

        greg, _jul, _rc = datcnv("G", 0, int(d150), self.branches)
        gg = greg % 100000000

        ig = integer_of_date(gg)
        ir = integer_of_date(gr)
        self.wdld = binary_truncate(ig - ir, 5)
        if self.wdld < 1:
            self.hit("B19")
            self.wmol = 0
        else:
            self.hit("B20")
            self.wmol = binary_truncate(int(truncate(Decimal(self.wdld) / 30 + 1, 0)), 3)

    # 2300-FTF
    def ftf(self, wupd: Decimal) -> Decimal:
        # cobc aligns the WUPD * 0.05 intermediate to 2 decimal places before
        # multiplying by WMOL (cob_decimal_align (d0, 2) in the generated C).
        wf51 = store(truncate(wupd * Decimal("0.05"), 2) * self.wmol, 11, 2)
        cap = wupd * Decimal("0.25")
        if wf51 > cap:
            self.hit("B21")
            wf51 = store(cap, 11, 2)
        else:
            self.hit("B22")
        return wf51

    # 2400-FTP
    def ftp(self, wupd: Decimal) -> Decimal:
        # cobc aligns the WUPD * 0.005 intermediate to 3 decimal places.
        wf52 = store(truncate(wupd * Decimal("0.005"), 3) * self.wmol, 11, 2)
        cap = wupd * Decimal("0.25")
        if wf52 > cap:
            self.hit("B23")
            wf52 = store(cap, 11, 2)
        else:
            self.hit("B24")
        return wf52

    # 2500-OFFSET
    def offset(self, wf51: Decimal, wf52: Decimal) -> Decimal:
        if wf52 > 0:
            self.hit("B25")
            wf51 = store(wf51 - wf52, 11, 2)
            if wf51 < 0:
                self.hit("B27")
                wf51 = Decimal(0)
            else:
                self.hit("B28")
        else:
            self.hit("B26")
        return wf51

    # 2600-MIN
    def minimum(
        self, mod: ModRecord, wupd: Decimal, wf51: Decimal, wf52: Decimal
    ) -> Decimal:
        if self.wdld <= 60:
            self.hit("B30")
            return wf51
        self.hit("B29")
        wmin = MINIMUM_PENALTY
        if wupd < wmin:
            self.hit("B31")
            wmin = wupd
        else:
            self.hit("B32")
        if wf51 < wmin:
            self.hit("B33")
            wf51 = store(wmin - wf52, 11, 2)
            self.counters.minimum += 1
            self.lines.append(
                report_line(
                    mod.ein, mod.mft, mod.txpd, "P502", "MINIMUM FTF APPLIED",
                    self.wmol, wf51, wf52,
                )
            )
        else:
            self.hit("B34")
        return wf51


def run(mod_in: bytes, trn_in: bytes) -> Result:
    """Run PENCALC over in-memory MODFTD and TRANIN images."""
    return _Pencalc(mod_in, trn_in).run()


def main(argv: list[str]) -> int:
    mod_path = Path(argv[1]) if len(argv) > 1 else Path("data/MODFTD.dat")
    trn_path = Path(argv[2]) if len(argv) > 2 else Path("data/TRANIN.dat")
    out_path = Path(argv[3]) if len(argv) > 3 else Path("data/MODPEN.dat")
    rpt_path = Path(argv[4]) if len(argv) > 4 else Path("data/PENCALC.rpt")

    result = run(mod_path.read_bytes(), trn_path.read_bytes())
    out_path.write_bytes(result.mod_out)
    rpt_path.write_text(result.report)

    print(f"PENCALC READ    {result.counters.read:06d}")
    print(f"PENCALC WRITTEN {result.counters.written:06d}")
    print(f"PENCALC FTF     {result.counters.ftf:06d}")
    print(f"PENCALC MINIMUM {result.counters.minimum:06d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
