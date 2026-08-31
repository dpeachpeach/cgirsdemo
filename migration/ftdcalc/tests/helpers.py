"""Small readers over FTDCALC output, used by the characterization tests."""

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ftdcalc import MOD_RECLEN, ModRecord, unpack_comp3  # noqa: E402


def module(modout: bytes, key: str) -> ModRecord:
    for offset in range(0, len(modout), MOD_RECLEN):
        record = ModRecord(modout[offset : offset + MOD_RECLEN])
        if record.key == key:
            return record
    raise AssertionError(f"module {key} not in output")


def pftd(modout: bytes, key: str) -> Decimal:
    return unpack_comp3(module(modout, key).raw[99:105], 2)


def lines_for(report: list[str], key: str) -> list[str]:
    ein, mft, txpd = key[0:9], key[9:11], key[11:17]
    prefix = f"FTDCALC  {ein} {mft} {txpd}"
    return [line for line in report if line.startswith(prefix)]


def amount_field(line: str) -> str:
    return line[72:83].strip()


def delinquency_field(line: str) -> str:
    return line[64:69].strip()


def tier_field(line: str) -> str:
    return line[70:71]


def code_field(line: str) -> str:
    return line[30:34]
