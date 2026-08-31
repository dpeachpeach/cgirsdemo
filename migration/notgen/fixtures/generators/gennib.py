"""Probe: how the GnuCOBOL runtime interprets each COMP-3 sign nibble."""
import sys
from decimal import Decimal

sys.path.insert(0, "migration/notgen")
import notgen  # noqa: E402


def rec(ein, nib):
    raw = notgen.pack_comp3(Decimal("5000.00"), 13, 2)
    assd = raw[:-1] + bytes([(raw[-1] & 0xF0) | nib])
    out = ein.encode() + b"01" + b"202409" + ein[:4].encode()
    out += ("SYN NIBBLE %X" % nib).ljust(35).encode() + b"C7" + b"        "
    for _ in range(3):
        out += notgen.pack_comp3(Decimal(2024001), 7, 0)
    out += assd + notgen.pack_comp3(Decimal(0), 13, 2) * 2
    out += notgen.pack_comp3(Decimal(0), 11, 2) * 4
    out += b" " * 8 + b"003" + b" " * 16
    assert len(out) == 150
    return out


R = [rec("9200000%02d" % nib, nib) for nib in range(0, 16)]
open("data/MODOFF.dat", "wb").write(b"".join(R))
print("wrote", len(R))
