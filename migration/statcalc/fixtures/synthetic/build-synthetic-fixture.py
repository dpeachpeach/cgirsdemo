"""Appends synthetic MODMAST fixture records for uncovered STATCALC branches."""
import sys

def rec(ein, mft, txpd, nctl, name, fsc, sic, frz, ased, rsed, csed,
        assd, dep, crd, pftd, pftf, pftp, intr, w8, tccnt):
    out = (f"{ein:09d}{mft:02d}{txpd}{nctl:<4}{name:<35}{fsc}{sic}{frz:<8}"
           f"{ased:07d}{rsed:07d}{csed:07d}{assd:013d}{dep:013d}{crd:013d}"
           f"{pftd:011d}{pftf:011d}{pftp:011d}{intr:011d}{w8:<8}{tccnt:03d}")
    assert len(out) == 181, len(out)
    return out

base = dict(nctl="SYNT", name="SYNTHETIC BRANCH FIXTURE CORP", fsc="1", sic="1",
            frz=" " * 8, ased=0, rsed=0, csed=0, assd=100000, dep=50000,
            crd=0, pftd=0, pftf=0, pftp=0, intr=0, tccnt=0)

rows = [
    rec(990000001, 1, "210002", w8="00X00000", **base),   # year 2100: /100 not /400
    rec(990000002, 1, "240002", w8="00X00000", **base),    # year 2400: /400 leap
    rec(990000003, 1, "209999", w8="00X00000", **base),    # month 99 -> DATCNV RC 8
    rec(990000004, 1, "202306", w8=" 7X00000", **base),    # SCC from blank+digit
    rec(990000005, 1, "202306", w8=" " * 8, **base),       # SCC from all blanks
]

with open("data/MODMAST.txt", "a") as fh:
    for r in rows:
        fh.write(r + "\n")
print("appended", len(rows), file=sys.stderr)
