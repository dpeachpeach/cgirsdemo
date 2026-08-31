"""Python port of src/ENTVAL.cbl (BMF entity validation, pipeline step 010).

Characterization port: behaviour mirrors the compiled COBOL, including its
defects. See reports/PORT-ENTVAL-<date>.md for the proposed fixes that are
deliberately NOT applied here.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

RECORD_LENGTH = 150
REPORT_LENGTH = 120

# copybooks/ENTREC.cpy offsets, zero-relative
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

# PFXTAB, three X(20) literals redefined as 30 occurrences of PIC 9(2).
PFXTAB = "10122026274546478182" "83848586878891929394" "95981113161735384344"
PFXENT = [PFXTAB[i:i + 2] for i in range(0, 60, 2)]

# NAMCTL 3000-SQUEEZE drops these and keeps everything else.
SQUEEZE_DROP = " ,.'-"

OPEN_FAIL_STATUS = "35"
OPEN_FAIL_RETURN_CODE = 16


def _fld(record: str, fld: tuple[int, int]) -> str:
    off, length = fld
    return record[off:off + length]


def _put(record: str, fld: tuple[int, int], value: str) -> str:
    off, length = fld
    value = value[:length].ljust(length)
    return record[:off] + value + record[off + length:]


def namctl(name: str) -> tuple[str, str]:
    """src/NAMCTL.cbl shim. Returns (NCP-NCTL, NCP-RC)."""
    wk01 = name[:35].ljust(35).upper()

    # 1000-CNTWD counts words into WK04, which nothing ever reads.
    wk04 = 0
    prev = " "
    for ch in wk01:
        if ch != " " and prev == " ":
            wk04 += 1
        prev = ch

    # 2000-DROPTHE: MOVE WK01(5:31) TO WK01 leaves four trailing spaces.
    if wk01[0:4] == "THE ":
        wk01 = wk01[4:35].ljust(35)

    # 3000-SQUEEZE
    wk02 = "".join(ch for ch in wk01 if ch not in SQUEEZE_DROP).ljust(35)[:35]

    if wk02 == " " * 35:
        return "    ", "8"
    return wk02[0:4], "0"


def _errlin(ein: str, code: str, text: str, old: str, new: str) -> str:
    line = (
        "ENTVAL"
        + "  "
        + ein[:9].ljust(9)
        + "  "
        + code[:4].ljust(4)
        + "  "
        + text[:40].ljust(40)
        + "  "
        + old[:4].ljust(4)
        + "  "
        + new[:4].ljust(4)
        + " " * 43
    )
    assert len(line) == REPORT_LENGTH
    return line


@dataclass
class EntvalResult:
    records: list[str] = field(default_factory=list)
    report: list[str] = field(default_factory=list)
    read_count: int = 0
    written_count: int = 0
    error_count: int = 0
    nc_corrected_count: int = 0
    return_code: int = 0
    console: list[str] = field(default_factory=list)

    @property
    def output_bytes(self) -> bytes:
        return "".join(self.records).encode("ascii")

    @property
    def report_text(self) -> str:
        # LINE SEQUENTIAL strips the trailing blanks of each written record.
        if not self.report:
            return ""
        return "".join(line.rstrip() + "\n" for line in self.report)


def _is_zero_fym(fym: str) -> bool:
    """ENT-FYM is PIC 9(2) compared against ZERO.

    A blank digit position is not zero to the runtime, so " 0", "0 " and "  "
    all fall through the default; only "00" is zero.
    """
    return fym == "00"


def edit_record(record: str, result: EntvalResult) -> str:
    """2100-EDIT: 2200-PFX, 2300-NCTL THRU 2300-X, 2400-FRC."""
    ein = _fld(record, F_EIN)

    # 2200-PFX
    wpfx = ein[0:2]
    wpsw = "N"
    for entry in PFXENT:
        if entry == wpfx:
            wpsw = "Y"
            break
    if wpsw == "N":
        result.report.append(
            _errlin(ein, "E101", "PREFIX NOT IN CAMPUS TABLE", "", "")
        )
        result.error_count += 1

    # 2300-NCTL
    derived, rc = namctl(_fld(record, F_NAME))
    stored = _fld(record, F_NCTL)
    if rc != "0":
        result.report.append(
            _errlin(ein, "E102", "NAME CONTROL NOT DERIVABLE", stored, "")
        )
        result.error_count += 1
    elif derived != stored:
        result.report.append(
            _errlin(
                ein,
                "E103",
                "NAME CONTROL MISMATCH - CORRECTED",
                stored,
                derived,
            )
        )
        result.nc_corrected_count += 1
        record = _put(record, F_NCTL, derived)

    # 2400-FRC
    if _fld(record, F_EC) == "F" and _fld(record, F_I_940) == "1":
        result.report.append(
            _errlin(ein, "E104", "EC F INCOMPATIBLE WITH 940 FRC", "", "")
        )
        result.error_count += 1
        record = _put(record, F_I_940, " ")

    if _is_zero_fym(_fld(record, F_FYM)):
        record = _put(record, F_FYM, "12")

    return record


def run(records: list[str]) -> EntvalResult:
    """0000-MAIN over an already-read ENTMAST.dat."""
    result = EntvalResult()
    for record in records:
        result.read_count += 1
        result.records.append(edit_record(record, result))
        result.written_count += 1
    result.console = [
        f"ENTVAL  READ    {result.read_count:06d}",
        f"ENTVAL  WRITTEN {result.written_count:06d}",
        f"ENTVAL  ERRORS  {result.error_count:06d}",
        f"ENTVAL  NC CORR {result.nc_corrected_count:06d}",
    ]
    return result


def split_records(data: bytes) -> list[str]:
    text = data.decode("ascii")
    if len(text) % RECORD_LENGTH:
        raise ValueError(f"ENTMAST.dat length {len(text)} is not a multiple of 150")
    return [
        text[i:i + RECORD_LENGTH] for i in range(0, len(text), RECORD_LENGTH)
    ]


def run_file(in_path: str) -> EntvalResult:
    """1000-INIT open failure path included: FS1 35 -> RETURN-CODE 16."""
    if not os.path.exists(in_path):
        result = EntvalResult()
        result.return_code = OPEN_FAIL_RETURN_CODE
        result.console = [f"ENTVAL OPEN FAIL ENTIN {OPEN_FAIL_STATUS}"]
        return result
    with open(in_path, "rb") as fh:
        return run(split_records(fh.read()))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    in_path = argv[0] if argv else "data/ENTMAST.dat"
    out_path = argv[1] if len(argv) > 1 else "data/ENTVAL.dat"
    rpt_path = argv[2] if len(argv) > 2 else "data/ENTERR.rpt"

    result = run_file(in_path)
    if result.return_code == 0:
        with open(out_path, "wb") as fh:
            fh.write(result.output_bytes)
        with open(rpt_path, "w") as fh:
            fh.write(result.report_text)
    for line in result.console:
        print(line)
    return result.return_code


if __name__ == "__main__":
    raise SystemExit(main())
