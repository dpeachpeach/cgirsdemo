#!/usr/bin/env python3
"""Append synthetic fixture records to the scratch copies of data/MODMAST.txt
and data/TRANIN.txt so that PENCALC branches unreached by the shipped fixtures
are executed. Keys stay above every shipped key so ascending order holds.
"""

MOD = []
TRN = []


def mod(ein, mft, txpd, assd, dep=0, crd=0, name="SYNTHETIC CASE"):
    rec = (
        "%09d" % ein
        + "%02d" % mft
        + "%06d" % txpd
        + "SYNT"
        + name.ljust(35)[:35]
        + "1"
        + "0"
        + " " * 8
        + "2027105"
        + "2027105"
        + "2034105"
        + "%013d" % round(assd * 100)
        + "%013d" % round(dep * 100)
        + "%013d" % round(crd * 100)
        + "%011d" % 0
        + "%011d" % 0
        + "%011d" % 0
        + "%011d" % 0
        + "SYN00000"
        + "000"
    )
    assert len(rec) == 181, len(rec)
    MOD.append(rec)


def trn(ein, mft, txpd, tc, dt, amt=0, cyc=202401, dln="SYNTHETIC00001"):
    rec = (
        "%09d" % ein
        + "%02d" % mft
        + "%06d" % txpd
        + "%03d" % tc
        + "%07d" % dt
        + "%013d" % round(amt * 100)
        + "%06d" % cyc
        + dln.ljust(14)[:14]
    )
    assert len(rec) == 60, len(rec)
    TRN.append(rec)


# S1 orphan transaction (skip loop) + module whose group has no TC 150
trn(990000010, 1, 202312, 650, 2024100, 100.00)
mod(990000011, 1, 202312, 5000.00, name="S1 NO TC150 PLUS ORPHAN")
trn(990000011, 1, 202312, 650, 2024100, 250.00)

# S2 TC 150 posted before the return due date -> WDLD < 1
mod(990000021, 1, 202312, 9000.00, name="S2 FILED EARLY")
trn(990000021, 1, 202312, 150, 2024010, 9000.00)

# S3 one month late -> WDLD 31, no caps
mod(990000031, 1, 202312, 10000.00, name="S3 ONE MONTH LATE")
trn(990000031, 1, 202312, 150, 2024046, 10000.00)

# S4 five years late -> both FTF and FTP capped at 25 pct
mod(990000041, 1, 201812, 100000.00, 20000.00, 5000.00, name="S4 CAPPED BOTH")
trn(990000041, 1, 201812, 150, 2024167, 100000.00)

# S5 one cent unpaid -> FTP truncates to zero, minimum floor clamps to balance
mod(990000051, 1, 202312, 0.01, name="S5 ONE CENT")
trn(990000051, 1, 202312, 150, 2024167, 0.01)

# S6 impossible julian day 400 -> DATCNV returns RC 8
mod(990000061, 1, 202312, 4000.00, name="S6 BAD JULIAN")
trn(990000061, 1, 202312, 150, 2024400, 4000.00)

# S7 century year 2100 (leap by 4, not by 400)
mod(990000071, 1, 202312, 3000.00, name="S7 YEAR 2100")
trn(990000071, 1, 202312, 150, 2100200, 3000.00)

# S8 year 2000 (leap by 400)
mod(990000081, 1, 202312, 2000.00, name="S8 YEAR 2000")
trn(990000081, 1, 202312, 150, 2000200, 2000.00)

# S9 two TC 150 postings in one group -> last one read wins
mod(990000085, 1, 202312, 10000.00, name="S9 TWO TC150")
trn(990000085, 1, 202312, 150, 2024046, 10000.00)
trn(990000085, 1, 202312, 150, 2024200, 10000.00)

# S10 delinquency past 1000 months -> WMOL overflows its PIC S9(3) COMP width
mod(990000086, 1, 202312, 3000.00, name="S10 YEAR 2130")
trn(990000086, 1, 202312, 150, 2130200, 3000.00)

# S11 balance beyond the penalty field width -> WF51/WF52 truncate high order
mod(990000087, 1, 202312, 99999999999.99, name="S11 FIELD OVERFLOW")
trn(990000087, 1, 202312, 150, 2024167, 0.00)

# S12 highest key, no transactions at all -> both loops fall through at EOF
mod(990000090, 1, 202312, 6000.00, name="S12 NO TRANSACTIONS")


def append(path, rows):
    with open(path, "a") as f:
        for r in rows:
            f.write(r + "\n")


append("data/MODMAST.txt", MOD)
append("data/TRANIN.txt", TRN)
print("appended %d module rows, %d transaction rows" % (len(MOD), len(TRN)))
