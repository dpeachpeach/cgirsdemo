"""Python port of src/CAWRMTCH.cbl — CAWR match, pipeline step 100.

Characterization port: this reproduces what the COBOL does, including the
places where what it does is not what the comments say it does. Behaviour is
byte-for-byte against the GnuCOBOL build of src/CAWRMTCH.cbl.

Reads  data/MODOFF.dat (150-byte BMFMOD records, COMP-3 packed amounts)
       data/CAWRW2.txt (44-byte unpacked SSA W-2 totals, line sequential)
Writes data/CAWRMTCH.rpt (line sequential, trailing blanks stripped)
"""

from decimal import Decimal, ROUND_DOWN
from pathlib import Path
import sys

MOD_RECORD_LEN = 150
W2_RECORD_LEN = 44
HIGH_VALUES = b"\xff" * 13

CENT = Decimal("0.01")

# copybooks/BMFMOD.cpy displacements, zero-relative
BMF_EIN = slice(0, 9)
BMF_MFT = slice(9, 11)
BMF_TXPD = slice(11, 17)
BMF_ASSD = slice(78, 85)  # S9(11)V99 COMP-3, 7 bytes


def unpack_comp3(raw, scale):
    """Decode COMP-3: two digits per byte, low nibble of the last byte is the sign."""
    nibbles = []
    for byte in raw:
        nibbles.append(byte >> 4)
        nibbles.append(byte & 0x0F)
    sign_nibble = nibbles.pop()
    digits = "".join(str(n) if n < 10 else "0" for n in nibbles)
    value = Decimal(digits).scaleb(-scale)
    if sign_nibble == 0x0D:
        value = -value
    return value


def truncate(value, int_digits, scale):
    """MOVE/COMPUTE into PIC S9(int_digits)V9(scale) with no ROUNDED: truncate
    the fraction toward zero and drop high-order digits that do not fit."""
    trunc = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_DOWN)
    limit = Decimal(10) ** int_digits
    magnitude = abs(trunc) % limit
    return -magnitude if trunc < 0 else magnitude


def edit_z9_99(value, signed=False):
    """PIC ZZZZZZZZ9.99 (12 chars), or ZZZZZZZZ9.99- (13) when signed."""
    negative = value < 0
    magnitude = abs(value).quantize(CENT, rounding=ROUND_DOWN)
    whole = int(magnitude) % 1_000_000_000
    cents = int((magnitude - int(magnitude)) * 100)
    out = f"{whole:>9}.{cents:02d}"
    if signed:
        out += "-" if negative else " "
    return out


def report_line(ein, year, code, text, w2_amt, liability, difference):
    line = (
        "CAWRMTCH"
        + "  "
        + f"{ein:>9}"
        + " "
        + f"{year:>4}"
        + "  "
        + f"{code:<4}"
        + "  "
        + f"{text:<24}"
        + "  "
        + edit_z9_99(w2_amt)
        + " "
        + edit_z9_99(liability)
        + " "
        + edit_z9_99(difference, signed=True)
        + " " * 15
    )
    return line.rstrip(" ")


class Cawrmtch:
    def __init__(self, mod_path, w2_path):
        self.mod_data = Path(mod_path).read_bytes()
        self.mod_pos = 0
        with open(w2_path, "rb") as handle:
            self.w2_lines = handle.read().splitlines()
        self.w2_pos = 0

        self.meof = False
        self.weof = False
        self.mkey = b"\x00" * 13
        self.wkey = b"\x00" * 13
        self.hkey = b"\x00" * 13
        self.assd = Decimal(0)

        self.wlia = Decimal(0)
        self.wnqt = 0
        self.wdif = Decimal(0)
        self.wtol = Decimal(0)

        self.hw_wage = Decimal(0)
        self.hw_whld = Decimal(0)
        self.hw_doc = 0
        self.w2_ein = "0" * 9
        self.w2_yr = "0" * 4

        self.c1 = self.c2 = self.c3 = self.c4 = self.c5 = 0
        self.lines = []

    # 0000-MAIN
    def run(self):
        self._rdmod()
        self._rdw2()
        while not (self.meof and self.weof):
            self._match()
        return self.lines

    # 2000-MATCH
    def _match(self):
        if self.mkey < self.wkey:
            self._group()
            self._941_only()
        elif self.mkey > self.wkey:
            self._w2_only()
            self._rdw2()
        else:
            self._group()
            self._compare()
            self._rdw2()

    # 3000-GRP
    def _group(self):
        self.hkey = self.mkey
        self.wlia = Decimal(0)
        self.wnqt = 0
        while not (self.meof or self.mkey != self.hkey):
            self.wlia = truncate(self.wlia + self.assd, 11, 2)
            self.wnqt += 1
            self._rdmod()
        self.c1 += 1

    # 4000-CMP
    def _compare(self):
        self.wdif = truncate(self.hw_whld - self.wlia, 11, 2)
        self.wtol = truncate(self.wlia * Decimal("0.01"), 11, 2)
        if self.wtol < 100:
            self.wtol = Decimal(100)
        ein = self.w2_ein
        year = self.hkey[9:13].decode("latin-1")
        if abs(self.wdif) <= self.wtol:
            self.c3 += 1
            code, text = "C001", "IN BALANCE"
        else:
            self.c5 += 1
            if self.wdif > 0:
                code, text = "C002", "W2 EXCEEDS 941 LIABILITY"
            else:
                code, text = "C003", "941 EXCEEDS W2 REPORTED"
        self.lines.append(
            report_line(ein, year, code, text, self.hw_whld, self.wlia, self.wdif)
        )

    # 4100-941ONLY
    def _941_only(self):
        self.c5 += 1
        ein = self.hkey[0:9].decode("latin-1")
        year = self.hkey[9:13].decode("latin-1")
        self.wdif = truncate(Decimal(0) - self.wlia, 11, 2)
        self.lines.append(
            report_line(
                ein, year, "C004", "NO W2 DATA FROM SSA", Decimal(0), self.wlia, self.wdif
            )
        )

    # 4200-W2ONLY
    def _w2_only(self):
        self.c4 += 1
        self.lines.append(
            report_line(
                self.w2_ein,
                self.w2_yr,
                "C005",
                "W2 FILED - NO 941 MODULE",
                self.hw_whld,
                Decimal(0),
                self.hw_whld,
            )
        )

    # 8100-RDMOD
    def _rdmod(self):
        fs1 = "N"
        while not self.meof:
            record = self._read_mod_record()
            if record is None:
                self.meof = True
                self.mkey = HIGH_VALUES
            else:
                mft = record[BMF_MFT].decode("latin-1")
                if mft.isdigit() and int(mft) == 1:
                    self.mkey = record[BMF_EIN] + record[BMF_TXPD][0:4]
                    self.assd = unpack_comp3(record[BMF_ASSD], 2)
                    fs1 = "Y"
            if fs1 == "Y":
                break

    def _read_mod_record(self):
        if self.mod_pos + MOD_RECORD_LEN > len(self.mod_data):
            return None
        record = self.mod_data[self.mod_pos : self.mod_pos + MOD_RECORD_LEN]
        self.mod_pos += MOD_RECORD_LEN
        return record

    # 8200-RDW2
    def _rdw2(self):
        if self.w2_pos >= len(self.w2_lines):
            self.weof = True
            self.wkey = HIGH_VALUES
            return
        line = self.w2_lines[self.w2_pos]
        self.w2_pos += 1
        record = line.ljust(W2_RECORD_LEN)[:W2_RECORD_LEN]
        self.c2 += 1
        self.w2_ein = record[0:9].decode("latin-1")
        self.w2_yr = record[9:13].decode("latin-1")
        self.wkey = record[0:9] + record[9:13]
        self.hw_wage = truncate(Decimal(record[13:26].decode("latin-1")).scaleb(-2), 11, 2)
        self.hw_whld = truncate(Decimal(record[26:39].decode("latin-1")).scaleb(-2), 11, 2)
        self.hw_doc = int(record[39:44])

    def counters(self):
        return [
            f"CAWRMTCH 941 GRP {self.c1:06d}",
            f"CAWRMTCH W2  REC {self.c2:06d}",
            f"CAWRMTCH MATCHED {self.c3:06d}",
            f"CAWRMTCH W2 ONLY {self.c4:06d}",
            f"CAWRMTCH DISCREP {self.c5:06d}",
        ]


def run_match(mod_path, w2_path, report_path=None):
    """Run the step. Returns (report lines, DISPLAY counter lines)."""
    job = Cawrmtch(mod_path, w2_path)
    lines = job.run()
    if report_path is not None:
        Path(report_path).write_text("".join(line + "\n" for line in lines))
    return lines, job.counters()


def main(argv):
    mod_path = argv[1] if len(argv) > 1 else "data/MODOFF.dat"
    w2_path = argv[2] if len(argv) > 2 else "data/CAWRW2.txt"
    report_path = argv[3] if len(argv) > 3 else "data/CAWRMTCH.rpt"
    _, counters = run_match(mod_path, w2_path, report_path)
    for line in counters:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
