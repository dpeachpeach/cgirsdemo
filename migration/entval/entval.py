"""Python port of the COBOL program ENTVAL (step 010 of the nightly entity run).

Characterization port: this module reproduces what ``src/ENTVAL.cbl`` and the
COBOL shim ``src/NAMCTL.cbl`` actually do, including their defects. It is not a
corrected implementation of IRM 3.13.2.

Record layout is ``copybooks/ENTREC.cpy`` (FB, LRECL 150). All fields in the
entity record are USAGE DISPLAY, so no packed-decimal unpacking is needed here;
the only arithmetic is the four PIC 9(6) run counters, which are integers.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List, Tuple

RECORD_LENGTH = 150
ERRLIN_LENGTH = 120

# copybooks/ENTREC.cpy, zero-relative offsets and lengths
F_EIN = (0, 9)
F_NAME = (9, 35)
F_NCTL = (44, 4)
F_SORT = (48, 4)
F_ADDR = (52, 35)
F_CITY = (87, 22)
F_ST = (109, 2)
F_ZIP = (111, 9)
F_FYM = (120, 2)
F_EC = (122, 1)
F_I_941 = (123, 1)
F_I_940 = (124, 1)
F_I_1120 = (125, 1)
F_I_720 = (126, 1)
F_XREF = (127, 9)
F_FILL = (136, 14)

# PFXTAB in ENTVAL: three X(20) literals redefined as PIC 9(02) OCCURS 30.
PFXTAB = ("10122026274546478182"
          "83848586878891929394"
          "95981113161735384344")
PFXENT: Tuple[int, ...] = tuple(
    int(PFXTAB[i:i + 2]) for i in range(0, len(PFXTAB), 2)
)

# ENTVAL error codes and their EL-TXT literals, PIC X(40).
E101 = ("E101", "PREFIX NOT IN CAMPUS TABLE")
E102 = ("E102", "NAME CONTROL NOT DERIVABLE")
E103 = ("E103", "NAME CONTROL MISMATCH - CORRECTED")
E104 = ("E104", "EC F INCOMPATIBLE WITH 940 FRC")

# NAMCTL 3000-SQUEEZE drops these characters outright.
SQUEEZE_DROP = (" ", ",", ".", "'", "-")


def _get(record: str, fld: Tuple[int, int]) -> str:
    off, ln = fld
    return record[off:off + ln]


def _put(record: str, fld: Tuple[int, int], value: str) -> str:
    off, ln = fld
    value = value[:ln].ljust(ln)
    return record[:off] + value + record[off + ln:]


def name_control(name: str) -> Tuple[str, str]:
    """NAMCTL shim: returns (NCP-NCTL, NCP-RC).

    Mirrors src/NAMCTL.cbl exactly, including the word count that 1000-CNTWD
    computes into WK04 and then never uses.
    """
    wk01 = name.upper()[:35].ljust(35)

    # 1000-CNTWD
    wk04 = 0
    wk05 = " "
    for n1 in range(35):
        wk03 = wk01[n1]
        if wk03 != " " and wk05 == " ":
            wk04 += 1
        wk05 = wk03

    # 2000-DROPTHE: unconditional, whatever the word count says.
    if wk01[:4] == "THE ":
        wk01 = wk01[4:4 + 31].ljust(35)

    # 3000-SQUEEZE
    wk02 = "".join(c for c in wk01 if c not in SQUEEZE_DROP).ljust(35)

    if wk02 == " " * 35:
        return "    ", "8"
    return wk02[:4], "0"


def _errlin(ein: str, code: str, text: str, old: str, new: str) -> str:
    line = ("ENTVAL" + "  " + ein + "  " + code[:4].ljust(4) + "  "
            + text[:40].ljust(40) + "  " + old[:4].ljust(4) + "  "
            + new[:4].ljust(4) + " " * 43)
    assert len(line) == ERRLIN_LENGTH
    return line


@dataclass
class RecordResult:
    output: str
    errors: List[str] = field(default_factory=list)
    error_count: int = 0
    nc_corrections: int = 0


@dataclass
class RunResult:
    outputs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    counters: dict = field(default_factory=dict)


def edit_record(record: str) -> RecordResult:
    """2100-EDIT for one entity record."""
    rec = record[:RECORD_LENGTH].ljust(RECORD_LENGTH)
    ein = _get(rec, F_EIN)
    errors: List[str] = []
    error_count = 0
    nc_corrections = 0

    # 2200-PFX
    wpfx = _get(rec, F_EIN)[:2]
    wpsw = "N"
    if wpfx.isdigit() and int(wpfx) in PFXENT:
        wpsw = "Y"
    if wpsw == "N":
        errors.append(_errlin(ein, E101[0], E101[1], "", ""))
        error_count += 1

    # 2300-NCTL THRU 2300-X
    derived, rc = name_control(_get(rec, F_NAME))
    if rc != "0":
        errors.append(_errlin(ein, E102[0], E102[1], _get(rec, F_NCTL), ""))
        error_count += 1
        # GO TO 2300-X: the mismatch edit below is skipped entirely.
    elif derived != _get(rec, F_NCTL):
        errors.append(
            _errlin(ein, E103[0], E103[1], _get(rec, F_NCTL), derived)
        )
        nc_corrections += 1
        rec = _put(rec, F_NCTL, derived)

    # 2400-FRC
    if _get(rec, F_EC) == "F" and _get(rec, F_I_940) == "1":
        errors.append(_errlin(ein, E104[0], E104[1], "", ""))
        error_count += 1
        rec = _put(rec, F_I_940, " ")
    fym = _get(rec, F_FYM)
    if fym.isdigit() and int(fym) == 0:
        rec = _put(rec, F_FYM, "12")

    return RecordResult(rec, errors, error_count, nc_corrections)


def run(records) -> RunResult:
    """0000-MAIN over an in-memory input file."""
    result = RunResult()
    r1 = r2 = r3 = r4 = 0
    for record in records:
        r1 += 1
        edited = edit_record(record)
        result.outputs.append(edited.output)
        result.errors.extend(edited.errors)
        r3 += edited.error_count
        r4 += edited.nc_corrections
        r2 += 1
    result.counters = {"read": r1, "written": r2, "errors": r3,
                       "nc_corr": r4}
    return result


def _read_fixed(path: str) -> List[str]:
    with open(path, "r", newline="") as fh:
        blob = fh.read()
    return [blob[i:i + RECORD_LENGTH]
            for i in range(0, len(blob), RECORD_LENGTH)]


def counter_lines(counters: dict) -> List[str]:
    """The four 9000-EOJ DISPLAY lines, PIC 9(6) zero filled."""
    return [
        "ENTVAL  READ    %06d" % counters["read"],
        "ENTVAL  WRITTEN %06d" % counters["written"],
        "ENTVAL  ERRORS  %06d" % counters["errors"],
        "ENTVAL  NC CORR %06d" % counters["nc_corr"],
    ]


def main(argv: List[str]) -> int:
    entin = argv[1] if len(argv) > 1 else "data/ENTMAST.dat"
    entot = argv[2] if len(argv) > 2 else "data/ENTVAL.dat"
    errpt = argv[3] if len(argv) > 3 else "data/ENTERR.rpt"

    if not os.path.exists(entin):
        # 1000-INIT: FILE STATUS 35 on OPEN INPUT of a missing file.
        print("ENTVAL OPEN FAIL ENTIN 35")
        return 16

    result = run(_read_fixed(entin))
    with open(entot, "w", newline="") as fh:
        fh.write("".join(result.outputs))
    with open(errpt, "w", newline="") as fh:
        for line in result.errors:
            fh.write(line.rstrip() + "\n")
    for line in counter_lines(result.counters):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
