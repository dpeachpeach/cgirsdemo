"""Python port of src/ENTVAL.cbl (BMF entity validation, step 010).

Behavioural port: whatever the COBOL does is what this does, defects included.
NAMCTL is ported from the COBOL shim src/NAMCTL.cbl, not from src/asm/NAMCTL.asm
(the HLASM does not execute in this corpus).

Record layout is copybooks/ENTREC.cpy, LRECL 150:
    EIN 9(9) 0-9, NAME X(35) 9-44, NCTL X(4) 44-48, SORT X(4) 48-52,
    ADDR X(35) 52-87, CITY X(22) 87-109, ST X(2) 109-111, ZIP 9(9) 111-120,
    FYM 9(2) 120-122, EC X(1) 122, IND X(4) 123-127 (941/940/1120/720),
    XREF 9(9) 127-136, FILL X(14) 136-150.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

RECLEN = 150

EIN = slice(0, 9)
NAME = slice(9, 44)
NCTL = slice(44, 48)
FYM = slice(120, 122)
EC = slice(122, 123)
I_941 = slice(123, 124)
I_940 = slice(124, 125)

PFXTAB = "10122026274546478182" "83848586878891929394" "95981113161735384344"
PFXENT = [PFXTAB[i:i + 2] for i in range(0, 60, 2)]

SQUEEZE_DROP = " ,.'-"


def namctl(name: str) -> tuple[str, str]:
    """Port of src/NAMCTL.cbl. Returns (NCP-NCTL, NCP-RC)."""
    wk01 = name.ljust(35)[:35].upper()

    # 1000-CNTWD counts words into WK04, which nothing ever reads.
    words = 0
    prev = " "
    for ch in wk01:
        if ch != " " and prev == " ":
            words += 1
        prev = ch

    # 2000-DROPTHE
    if wk01[0:4] == "THE ":
        wk01 = wk01[4:35].ljust(35)

    # 3000-SQUEEZE
    wk02 = "".join(ch for ch in wk01 if ch not in SQUEEZE_DROP).ljust(35)[:35]

    if wk02.strip() == "":
        return " " * 4, "8"
    return wk02[0:4], "0"


def errlin(ein: str, cod: str, txt: str, old: str, new: str) -> str:
    """ERRLIN, PIC X(120), written to a LINE SEQUENTIAL file (trailing blanks cut)."""
    line = (
        "ENTVAL"
        + "  "
        + ein.ljust(9)[:9]
        + "  "
        + cod.ljust(4)[:4]
        + "  "
        + txt.ljust(40)[:40]
        + "  "
        + old.ljust(4)[:4]
        + "  "
        + new.ljust(4)[:4]
        + " " * 43
    )
    return line[:120].rstrip()


@dataclass
class Counters:
    r1: int = 0  # read
    r2: int = 0  # written
    r3: int = 0  # errors
    r4: int = 0  # name control corrections


@dataclass
class EditResult:
    record: str
    errors: list[str] = field(default_factory=list)
    error_count: int = 0
    nc_corrections: int = 0


def edit_record(rec: str) -> EditResult:
    """2100-EDIT: 2200-PFX, 2300-NCTL THRU 2300-X, 2400-FRC."""
    rec = rec.ljust(RECLEN)[:RECLEN]
    out = EditResult(record=rec)

    ein = rec[EIN]

    # 2200-PFX
    wpfx = ein[0:2]
    if wpfx not in PFXENT:
        out.errors.append(
            errlin(ein, "E101", "PREFIX NOT IN CAMPUS TABLE", " " * 4, " " * 4)
        )
        out.error_count += 1

    # 2300-NCTL
    nctl, rc = namctl(rec[NAME])
    if rc != "0":
        out.errors.append(
            errlin(ein, "E102", "NAME CONTROL NOT DERIVABLE", rec[NCTL], " " * 4)
        )
        out.error_count += 1
    elif nctl != rec[NCTL]:
        out.errors.append(
            errlin(
                ein,
                "E103",
                "NAME CONTROL MISMATCH - CORRECTED",
                rec[NCTL],
                nctl,
            )
        )
        out.nc_corrections += 1
        rec = rec[:44] + nctl + rec[48:]

    # 2400-FRC
    if rec[EC] == "F" and rec[I_940] == "1":
        out.errors.append(
            errlin(ein, "E104", "EC F INCOMPATIBLE WITH 940 FRC", " " * 4, " " * 4)
        )
        out.error_count += 1
        rec = rec[:124] + " " + rec[125:]

    if rec[FYM] == "00":
        rec = rec[:120] + "12" + rec[122:]

    out.record = rec
    return out


def read_records(path: str) -> list[str]:
    """ENTMAST.dat is unblocked fixed 150-byte records; the .txt fixture is the
    same layout one record per line (BLDFIX copies entity records verbatim)."""
    with open(path, "r", newline="") as fh:
        raw = fh.read()
    if "\n" in raw:
        return [ln.ljust(RECLEN)[:RECLEN] for ln in raw.split("\n") if ln.strip() != ""]
    return [raw[i:i + RECLEN].ljust(RECLEN) for i in range(0, len(raw), RECLEN)]


def run(
    in_path: str = "data/ENTMAST.dat",
    out_path: str = "data/ENTVAL.dat",
    rpt_path: str = "data/ENTERR.rpt",
) -> Counters:
    """0000-MAIN. Raises FileNotFoundError where the COBOL takes the FS1 path."""
    if not os.path.exists(in_path):
        raise FileNotFoundError(in_path)

    cnt = Counters()
    out_recs: list[str] = []
    rpt_lines: list[str] = []

    for rec in read_records(in_path):
        cnt.r1 += 1
        res = edit_record(rec)
        rpt_lines.extend(res.errors)
        cnt.r3 += res.error_count
        cnt.r4 += res.nc_corrections
        out_recs.append(res.record)
        cnt.r2 += 1

    with open(out_path, "w", newline="") as fh:
        fh.write("".join(out_recs))
    with open(rpt_path, "w", newline="") as fh:
        for line in rpt_lines:
            fh.write(line + "\n")
    return cnt


def main(argv: list[str]) -> int:
    args = argv[1:]
    in_path = args[0] if len(args) > 0 else "data/ENTMAST.dat"
    out_path = args[1] if len(args) > 1 else "data/ENTVAL.dat"
    rpt_path = args[2] if len(args) > 2 else "data/ENTERR.rpt"
    try:
        cnt = run(in_path, out_path, rpt_path)
    except FileNotFoundError:
        print("ENTVAL OPEN FAIL ENTIN 35")
        return 16
    print(f"ENTVAL  READ    {cnt.r1:06d}")
    print(f"ENTVAL  WRITTEN {cnt.r2:06d}")
    print(f"ENTVAL  ERRORS  {cnt.r3:06d}")
    print(f"ENTVAL  NC CORR {cnt.r4:06d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
