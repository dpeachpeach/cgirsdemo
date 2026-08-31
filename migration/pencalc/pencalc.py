"""PENCALC - failure to file / failure to pay penalty, IRC 6651, step 050.

Python port of src/PENCALC.cbl (GnuCOBOL 3.1.2, compiled -std=ibm, fixed
format). The COBOL is the specification: this module reproduces its observable
behaviour, defects included. Arithmetic is Decimal throughout and follows the
intermediate truncation the compiler emits for each statement, not the
mathematical result:

    COMPUTE WF51 = WUPD * 0.05  * WMOL   -> cob_decimal_align(d0, 2) after 0.05
    COMPUTE WF52 = WUPD * 0.005 * WMOL   -> cob_decimal_align(d0, 3) after 0.005

so the product with WMOL is taken from an already-truncated intermediate.
Stores into COMP-3 fields truncate toward zero at the field scale and drop
high-order digits beyond the field width; COMP (binary) fields are compiled
with binary-truncate off and keep their full binary value.
"""

from decimal import Decimal
import datetime

MOD_LRECL = 150
TRN_LRECL = 80
RPT_LRECL = 120

# 2600-MIN carries this floor as a literal. See the report for the drift.
MINIMUM_PENALTY = Decimal("485.00")

DTAB = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

_EPOCH = datetime.date(1600, 12, 31).toordinal()


def unpack_comp3(raw, scale, signed):
    """Decode a COMP-3 field. Unsigned fields carry an 0xF sign nibble."""
    digits = "".join("%02x" % b for b in raw)
    sign_nibble = digits[-1]
    value = int(digits[:-1] or "0")
    if signed and sign_nibble in ("b", "d"):
        value = -value
    return Decimal(value).scaleb(-scale)


def pack_comp3(value, digits, scale, signed):
    """Store a Decimal into a COMP-3 field the way cob_decimal_get_field does:
    truncate toward zero at the field scale, then keep the low-order digits."""
    scaled = int(value.scaleb(scale).to_integral_value(rounding="ROUND_DOWN"))
    negative = scaled < 0
    scaled = abs(scaled) % (10 ** digits)
    if signed:
        sign_nibble = "d" if negative else "c"
    else:
        sign_nibble = "f"
    text = str(scaled).rjust(digits, "0") + sign_nibble
    if len(text) % 2:
        text = "0" + text
    return bytes.fromhex(text)


def store(value, digits, scale):
    """Truncating store into a signed COMP-3 field, returned as a Decimal."""
    return unpack_comp3(pack_comp3(value, digits, scale, True), scale, True)


def integer_of_date(yyyymmdd):
    """FUNCTION INTEGER-OF-DATE: days since 1600-12-31, zero when invalid."""
    year, month, day = (
        yyyymmdd // 10000,
        (yyyymmdd // 100) % 100,
        yyyymmdd % 100,
    )
    if not 1601 <= year <= 9999 or not 1 <= month <= 12 or day < 1:
        return 0
    try:
        return datetime.date(year, month, day).toordinal() - _EPOCH
    except ValueError:
        return 0


def _leap(year):
    """DATCNV 3000-LEAP."""
    if year % 4:
        return 0
    if year % 100:
        return 1
    return 1 if year % 400 == 0 else 0


def datcnv_to_gregorian(julian):
    """DATCNV 2000-TOGRG. Returns None when the shim sets DCP-RC to '8'; the
    caller keeps whatever DCP-GREG already held, which PENCALC zeroed."""
    ky = julian // 1000
    ka = julian - ky * 1000
    kl = _leap(ky)
    if ka < 1 or ka > 365 + kl:
        return None
    km = 1
    while km <= 12:
        kr = DTAB[km - 1]
        if km == 2:
            kr += kl
        if ka <= kr:
            break
        ka -= kr
        km += 1
    return ky * 10000 + km * 100 + ka


class ModuleRecord:
    """BMFMOD copybook, 150 bytes. Only the fields PENCALC touches are decoded;
    the rest of the record is carried through untouched."""

    EIN = slice(0, 9)
    MFT = slice(9, 11)
    TXPD = slice(11, 17)
    ASSD = slice(78, 85)
    DEP = slice(85, 92)
    CRD = slice(92, 99)
    PFTF = slice(105, 111)
    PFTP = slice(111, 117)

    def __init__(self, raw):
        self.raw = bytearray(raw)

    @property
    def key(self):
        return bytes(self.raw[0:17])

    @property
    def ein(self):
        return self.raw[self.EIN].decode("ascii")

    @property
    def mft(self):
        return self.raw[self.MFT].decode("ascii")

    @property
    def txpd(self):
        return self.raw[self.TXPD].decode("ascii")

    @property
    def assd(self):
        return unpack_comp3(self.raw[self.ASSD], 2, True)

    @property
    def dep(self):
        return unpack_comp3(self.raw[self.DEP], 2, True)

    @property
    def crd(self):
        return unpack_comp3(self.raw[self.CRD], 2, True)

    def set_pftf(self, value):
        self.raw[self.PFTF] = pack_comp3(value, 11, 2, True)

    def set_pftp(self, value):
        self.raw[self.PFTP] = pack_comp3(value, 11, 2, True)


class TransactionRecord:
    """TRANREC copybook, 80 bytes."""

    def __init__(self, raw):
        self.raw = bytes(raw)

    @property
    def key(self):
        return self.raw[0:17]

    @property
    def tc(self):
        return int(self.raw[17:20])

    @property
    def dt(self):
        return int(self.raw[20:27])


def _edit_amount(value):
    """PIC ZZZZZZ9.99 receiving a signed S9(9)V99 field: the sign is dropped and
    the two high-order digits do not fit."""
    cents = abs(int(value.scaleb(2).to_integral_value(rounding="ROUND_DOWN")))
    whole, frac = divmod(cents % 10 ** 11, 100)
    return "%7d.%02d" % (whole % 10 ** 7, frac)


def _edit_months(value):
    """PIC ZZ9 receiving S9(3) COMP: three digits, sign dropped."""
    months = abs(int(value)) % 1000
    return "%3d" % months


def report_line(module, code, text, months, ftf, ftp):
    line = (
        "PENCALC"
        + "  "
        + module.ein
        + " "
        + module.mft
        + " "
        + module.txpd
        + "  "
        + code.ljust(4)
        + "  "
        + text.ljust(24)
        + "  "
        + _edit_months(months)
        + " "
        + _edit_amount(ftf)
        + " "
        + _edit_amount(ftp)
        + " " * 30
    )
    return line[:RPT_LRECL]


class Pencalc:
    """The program's WORKING-STORAGE lives here because 2200-MONTHS leaves WDLD
    untouched when there is no TC 150, exactly as the COBOL does."""

    def __init__(self):
        self.read_count = 0
        self.written_count = 0
        self.ftf_count = 0
        self.minimum_count = 0
        self.report = []
        self.wdld = 0
        self.wmol = 0
        self.wupd = Decimal(0)
        self.wf51 = Decimal(0)
        self.wf52 = Decimal(0)
        self.wmin = Decimal(0)
        self.d150 = 0
        self._trn = None
        self._tkey = None
        self._teof = False

    # 8100-RDTRN
    def _read_trn(self):
        try:
            self._trn = next(self._trn_iter)
        except StopIteration:
            self._trn = None
            self._teof = True
            self._tkey = b"\xff" * 17
            return
        self._tkey = self._trn.key

    def run(self, modules, transactions):
        self._trn_iter = iter(transactions)
        self._read_trn()
        out = []
        for module in modules:
            self.read_count += 1
            self._process(module)
            out.append(bytes(module.raw))
            self.written_count += 1
        return out, self.report

    # 2100-PEN
    def _process(self, module):
        mkey = module.key
        self.d150 = 0
        self.wf51 = Decimal(0)
        self.wf52 = Decimal(0)
        self.wmin = Decimal(0)
        self.wmol = 0

        while not self._teof and self._tkey < mkey:
            self._read_trn()
        while not self._teof and self._tkey == mkey:
            if self._trn.tc == 150:
                self.d150 = self._trn.dt
            self._read_trn()

        self.wupd = store(module.assd - module.dep - module.crd, 13, 2)
        if self.wupd < 0:
            self.wupd = Decimal(0)

        self._months(module)

        if self.wmol > 0 and self.wupd > 0:
            self._ftf()
            self._ftp()
            self._offset()
            self._minimum(module)
            module.set_pftf(self.wf51)
            module.set_pftp(self.wf52)
            self.ftf_count += 1
            self.report.append(
                report_line(
                    module,
                    "P501",
                    "FTF/FTP ASSESSED",
                    self.wmol,
                    self.wf51,
                    self.wf52,
                )
            )

    # 2200-MONTHS
    def _months(self, module):
        if self.d150 == 0:
            self.wmol = 0
            return
        vy = int(module.txpd[0:4])
        vm = int(module.txpd[4:6])
        vm += 1
        if vm > 12:
            vm -= 12
            vy += 1
        gr = vy * 10000 + vm * 100 + 15
        gg = datcnv_to_gregorian(self.d150)
        if gg is None:
            gg = 0
        ig = integer_of_date(gg)
        ir = integer_of_date(gr)
        self.wdld = ig - ir
        if self.wdld < 1:
            self.wmol = 0
        else:
            self.wmol = self.wdld // 30 + 1

    # 2300-FTF
    def _ftf(self):
        rate = (self.wupd * Decimal("0.05")).quantize(
            Decimal("0.01"), rounding="ROUND_DOWN"
        )
        self.wf51 = store(rate * self.wmol, 11, 2)
        if self.wf51 > self.wupd * Decimal("0.25"):
            self.wf51 = store(self.wupd * Decimal("0.25"), 11, 2)

    # 2400-FTP
    def _ftp(self):
        rate = (self.wupd * Decimal("0.005")).quantize(
            Decimal("0.001"), rounding="ROUND_DOWN"
        )
        self.wf52 = store(rate * self.wmol, 11, 2)
        if self.wf52 > self.wupd * Decimal("0.25"):
            self.wf52 = store(self.wupd * Decimal("0.25"), 11, 2)

    # 2500-OFFSET
    def _offset(self):
        if self.wf52 > 0:
            self.wf51 = store(self.wf51 - self.wf52, 11, 2)
            if self.wf51 < 0:
                self.wf51 = Decimal(0)

    # 2600-MIN
    def _minimum(self, module):
        if self.wdld > 60:
            self.wmin = MINIMUM_PENALTY
            if self.wupd < self.wmin:
                self.wmin = store(self.wupd, 11, 2)
            if self.wf51 < self.wmin:
                self.wf51 = store(self.wmin, 11, 2)
                self.wf51 = store(self.wf51 - self.wf52, 11, 2)
                self.minimum_count += 1
                self.report.append(
                    report_line(
                        module,
                        "P502",
                        "MINIMUM FTF APPLIED",
                        self.wmol,
                        self.wf51,
                        self.wf52,
                    )
                )


def read_fixed(path, lrecl, factory):
    with open(path, "rb") as handle:
        data = handle.read()
    return [
        factory(data[i:i + lrecl]) for i in range(0, len(data) - lrecl + 1, lrecl)
    ]


def run_files(modin, trnin, modout, rptout):
    modules = read_fixed(modin, MOD_LRECL, ModuleRecord)
    transactions = read_fixed(trnin, TRN_LRECL, TransactionRecord)
    engine = Pencalc()
    records, report = engine.run(modules, transactions)
    with open(modout, "wb") as handle:
        handle.write(b"".join(records))
    with open(rptout, "w", newline="\n") as handle:
        for line in report:
            handle.write(line.rstrip(" ") + "\n")
    return engine


def main():
    engine = run_files(
        "data/MODFTD.dat", "data/TRANIN.dat", "data/MODPEN.dat", "data/PENCALC.rpt"
    )
    print("PENCALC READ    %06d" % engine.read_count)
    print("PENCALC WRITTEN %06d" % engine.written_count)
    print("PENCALC FTF     %06d" % engine.ftf_count)
    print("PENCALC MINIMUM %06d" % engine.minimum_count)


if __name__ == "__main__":
    main()
