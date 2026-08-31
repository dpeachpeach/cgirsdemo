"""Scratch-tree generator: builds a synthetic MODOFF.dat exercising NOTGEN
branches the shipped fixtures never reach. Run bin/NOTGEN afterwards to capture
the COBOL's output as the golden expectation."""
import sys
from decimal import Decimal

sys.path.insert(0, "migration/notgen")
import notgen  # noqa: E402

D = Decimal


def rec(ein, mft, txpd, nctl, name, frz, assd, dep, crd, pftd, pftf, pftp, itr):
    out = ein.encode() + mft.encode() + txpd.encode()
    out += nctl.ljust(4).encode() + name.ljust(35)[:35].encode()
    out += b"C" + b"7"
    out += frz.ljust(8)[:8].encode()
    for jul in (2024001, 2025001, 2026001):
        out += notgen.pack_comp3(D(jul), 7, 0)
    for amt in (assd, dep, crd):
        out += notgen.pack_comp3(D(amt), 13, 2)
    for amt in (pftd, pftf, pftp, itr):
        out += notgen.pack_comp3(D(amt), 11, 2)
    out += b" " * 8 + b"003" + b" " * 16
    assert len(out) == 150, len(out)
    return out


CASES = [
    # id, frz, assd, dep, crd, pftd, pftf, pftp, int
    ("900000001", "01", "202312", "     ", "0.00", "0", "0", "0", "0", "0"),
]

R = []
def add(ein, mft, txpd, name, frz, assd, dep, crd, pftd, pftf, pftp, itr):
    R.append(rec(ein, mft, txpd, ein[:4], name, frz, assd, dep, crd, pftd, pftf, pftp, itr))


# S01 plain balance due over 100 -> CP 0161
add("900000001", "01", "202312", "SYN BALANCE DUE CORP", "        ", "5000.00", "1000.00", "0", "0", "0", "0", "0")
# S02 balance exactly 100.00 -> no notice
add("900000002", "01", "202312", "SYN BOUNDARY HIGH", "        ", "1100.00", "1000.00", "0", "0", "0", "0", "0")
# S03 balance 100.01 -> CP 0161
add("900000003", "01", "202312", "SYN BOUNDARY HIGH PLUS", "        ", "1100.01", "1000.00", "0", "0", "0", "0", "0")
# S04 balance -100.00 -> no notice
add("900000004", "01", "202312", "SYN BOUNDARY LOW", "        ", "900.00", "1000.00", "0", "0", "0", "0", "0")
# S05 balance -100.01 -> CP 0267
add("900000005", "01", "202312", "SYN BOUNDARY LOW MINUS", "        ", "899.99", "1000.00", "0", "0", "0", "0", "0")
# S06 CP 0267 with R freeze only -> suppressed
add("900000006", "01", "202312", "SYN REFUND FREEZE R", "   R    ", "0.00", "5000.00", "0", "0", "0", "0", "0")
# S07 CP 0267 with Z freeze only -> suppressed
add("900000007", "01", "202312", "SYN Z FREEZE ONLY", "      Z ", "0.00", "5000.00", "0", "0", "0", "0", "0")
# S08 CP 0161 with R freeze -> NOT suppressed
add("900000008", "01", "202312", "SYN BALDUE WITH R", "   R    ", "5000.00", "0", "0", "0", "0", "0", "0")
# S09 CP 0193 with Z freeze -> suppressed
add("900000009", "01", "202312", "SYN DUP WITH Z", "A     Z ", "7500.00", "0", "0", "0", "0", "0", "0")
# S10 PFTD and PFTF both positive -> 0194 wins
add("900000010", "01", "202312", "SYN FTD AND FTF", "        ", "1000.00", "0", "0", "250.00", "375.00", "0", "0")
# S11 PFTF only -> 0215
add("900000011", "01", "202312", "SYN FTF ONLY", "        ", "1000.00", "0", "0", "0", "410.55", "0", "0")
# S12 negative PFTD, balance over 100 -> 0161
add("900000012", "01", "202312", "SYN NEGATIVE FTD", "        ", "5000.00", "0", "0", "-250.00", "0", "0", "0")
# S13 all zeros -> no notice
add("900000013", "01", "202312", "SYN ALL ZERO", "        ", "0", "0", "0", "0", "0", "0", "0")
# S14 balance over 999,999,999.99 -> report edit truncation, CP 0161
add("900000014", "01", "202312", "SYN HUGE POSITIVE", "        ", "12345678901.23", "0", "0", "0", "0", "0", "0")
# S15 huge negative balance -> CP 0267 with edit truncation
add("900000015", "01", "202312", "SYN HUGE NEGATIVE", "        ", "0", "98765432109.87", "0", "0", "0", "0", "0")
# S16 CP 0193 severity 3 with large negative balance
add("900000016", "01", "202312", "SYN FREEZE A NEGATIVE", "A       ", "0", "44444.44", "0", "0", "0", "0", "0")
# S17 arithmetic overflow past 11 integer digits
add("900000017", "01", "202312", "SYN OVERFLOW", "        ", "99999999999.99", "0", "0", "999999999.99", "0", "0", "0")
# S18 lowercase a in freeze A position -> not the A branch
add("900000018", "01", "202312", "SYN LOWERCASE A", "a       ", "5000.00", "0", "0", "0", "0", "0", "0")
# S19 PFTD positive with R freeze -> not suppressed
add("900000019", "01", "202312", "SYN FTD WITH R", "   R    ", "1000.00", "0", "0", "10.00", "0", "0", "0")
# S20 CP 0267 with both R and Z
add("900000020", "01", "202312", "SYN R AND Z", "   R  Z ", "0", "9000.00", "0", "0", "0", "0", "0")
# S21 credits and interest drive the balance negative
add("900000021", "01", "202312", "SYN CREDIT DRIVEN", "        ", "10000.00", "0", "9000.00", "0", "0", "0", "2000.00")
# S22 PFTP alone cannot select a notice unless balance qualifies
add("900000022", "01", "202312", "SYN FTP ONLY SMALL", "        ", "0", "0", "0", "0", "0", "50.00", "0")
# S23 PFTP alone pushing balance over 100
add("900000023", "12", "202506", "SYN FTP ONLY LARGE", "        ", "0", "0", "0", "0", "0", "150.00", "0")
# S24 freeze A with R -> A wins, no suppression
add("900000024", "01", "202312", "SYN A AND R", "A  R    ", "0", "6000.00", "0", "0", "0", "0", "0")

open("data/MODOFF.dat", "wb").write(b"".join(R))
print("wrote", len(R), "synthetic records")
