"""Second synthetic batch: COMP-3 sign-nibble variants and intermediate-width
overflow, captured against the COBOL."""
import sys
from decimal import Decimal

sys.path.insert(0, "migration/notgen")
import notgen  # noqa: E402

D = Decimal


def p3(value, digits, scale, sign_nibble=None):
    raw = notgen.pack_comp3(D(value), digits, scale)
    if sign_nibble is None:
        return raw
    return raw[:-1] + bytes([(raw[-1] & 0xF0) | sign_nibble])


def rec(ein, mft, txpd, name, frz, assd, dep, crd, pftd, pftf, pftp, itr,
        assd_sign=None, pftd_sign=None):
    out = ein.encode() + mft.encode() + txpd.encode()
    out += ein[:4].encode() + name.ljust(35)[:35].encode() + b"C7"
    out += frz.ljust(8)[:8].encode()
    for jul in (2024001, 2025001, 2026001):
        out += p3(jul, 7, 0, 0x0F)
    out += p3(assd, 13, 2, assd_sign)
    out += p3(dep, 13, 2)
    out += p3(crd, 13, 2)
    out += p3(pftd, 11, 2, pftd_sign)
    out += p3(pftf, 11, 2)
    out += p3(pftp, 11, 2)
    out += p3(itr, 11, 2)
    out += b" " * 8 + b"003" + b" " * 16
    assert len(out) == 150, len(out)
    return out


R = []
# T01 unsigned sign nibble 0xF on BMF-ASSD -> read as positive
R.append(rec("910000001", "01", "202409", "SYN SIGN NIBBLE F", "        ",
             "7250.00", "0", "0", "0", "0", "0", "0", assd_sign=0x0F))
# T02 alternate negative nibble 0xB on BMF-PFTD -> negative, so not > ZERO
R.append(rec("910000002", "01", "202409", "SYN SIGN NIBBLE B", "        ",
             "9000.00", "0", "0", "-125.00", "0", "0", "0", pftd_sign=0x0B))
# T03 alternate positive nibble 0xA on BMF-ASSD
R.append(rec("910000003", "01", "202409", "SYN SIGN NIBBLE A", "        ",
             "6100.00", "0", "0", "0", "0", "0", "0", assd_sign=0x0A))
# T04 WLIA overflows 11 integer digits before WBAL is computed
R.append(rec("910000004", "01", "202409", "SYN LIA OVERFLOW", "        ",
             "99999999999.99", "0", "0", "999999999.99", "999999999.99",
             "999999999.99", "0"))
# T05 large deposit drives WBAL negative past the edit width
R.append(rec("910000005", "07", "199812", "SYN OLD PERIOD", "        ",
             "1.00", "1000000000.00", "0", "0", "0", "0", "0"))
# T06 MFT 00 and interest only
R.append(rec("910000006", "00", "202409", "SYN MFT ZERO", "        ",
             "0", "0", "0", "0", "0", "0", "500.00"))
# T07 every freeze byte set
R.append(rec("910000007", "01", "202409", "SYN ALL FREEZES", "AVLRSXZO",
             "0", "3000.00", "0", "0", "0", "0", "0"))
# T08 freeze Z with no notice selected -> Z does not create a report line
R.append(rec("910000008", "01", "202409", "SYN Z NO NOTICE", "      Z ",
             "50.00", "0", "0", "0", "0", "0", "0"))
# T09 negative interest increases the balance
R.append(rec("910000009", "01", "202409", "SYN NEGATIVE INTEREST", "        ",
             "0", "0", "0", "0", "0", "0", "-2500.00"))
# T10 name field at full 35 characters
R.append(rec("910000010", "01", "202409", "SYN THIRTY FIVE CHARACTER NAME ABCD",
             "        ", "4000.00", "0", "0", "0", "0", "0", "0"))

open("data/MODOFF.dat", "wb").write(b"".join(R))
print("wrote", len(R), "records")
