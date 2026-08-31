#!/usr/bin/env python3
"""Builds the synthetic fixture set (scenario B) in the scratch tree."""


def mod(ein, mft, txpd, nctl, name, fsc, sic, frz, ased, rsed, csed,
        assd=0, dep=0, crd=0, pftd=0, pftf=0, pftp=0, intr=0, w8="        ",
        tccnt=0):
    return (
        f"{ein:09d}{mft:02d}{txpd:06d}{nctl:<4}{name:<35}{fsc:1}{sic:1}"
        f"{frz:<8}{ased:07d}{rsed:07d}{csed:07d}"
        f"{assd:013d}{dep:013d}{crd:013d}"
        f"{pftd:011d}{pftf:011d}{pftp:011d}{intr:011d}{w8:<8}{tccnt:03d}"
    )


def trn(ein, mft, txpd, tc, dt, amt=0, cyc=202401, dln="X" * 14):
    return (f"{ein:09d}{mft:02d}{txpd:06d}{tc:03d}{dt:07d}"
            f"{amt:013d}{cyc:06d}{dln:<14}")


mods = [
    # M1: TC 150 + TC 977, no TC 976 -> duplicate found through the C77 leg
    mod(700000001, 1, 202312, "ACME", "ACME ANVIL CORP", "1", "2",
        "        ", 2027105, 2027105, 2034105, tccnt=5),
    # M2: two TC 150 -> duplicate through the C50 > 1 leg; TCCNT at 998 wraps
    mod(700000002, 1, 202312, "BETA", "BETA BOLT LLC", "1", "3",
        "        ", 2027105, 2027105, 2034105, tccnt=998),
    # M3: TC 560 whose date is not later than the module ASED -> no correction
    mod(700000003, 1, 202312, "GAMM", "GAMMA GEAR INC", "1", "4",
        "        ", 2030105, 2030105, 2037105, tccnt=0),
    # M4: no transactions at all and positioned after transaction EOF
    mod(700000004, 1, 202312, "DELT", "DELTA DRILL PA", "2", "5",
        "        ", 2027105, 2027105, 2034105, tccnt=0),
]

trns = [
    # orphan transactions below every module key -> consumed by 2200-SKIP
    trn(600000000, 1, 202301, 150, 2024106),
    trn(600000000, 1, 202301, 976, 2024146),
    # M1
    trn(700000001, 1, 202312, 150, 2024106),
    trn(700000001, 1, 202312, 290, 2024110),
    trn(700000001, 1, 202312, 977, 2024150),
    # M2
    trn(700000002, 1, 202312, 150, 2024106),
    trn(700000002, 1, 202312, 150, 2024180),
    # M3
    trn(700000003, 1, 202312, 560, 2029105),
]

with open("data/MODMAST.txt", "w") as f:
    for m in mods:
        assert len(m) == 181, len(m)
        f.write(m + "\n")
with open("data/TRANIN.txt", "w") as f:
    for t in trns:
        assert len(t) == 60, len(t)
        f.write(t + "\n")
print("synthetic fixtures written")
