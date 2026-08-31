"""Build the synthetic-augmented fixture set in a scratch tree.

Adds fixture records to data/MODMAST.txt and data/TRANIN.txt that satisfy the
preconditions of the FTDCALC branches the shipped fixtures never reach.
"""
import sys

MOD_NAME = "SYNTHETIC BRANCH PROBE CORP"


def mod(ein, txpd, assd_cents, sic="0", frz=" " * 8, w8="05B00000"):
    fields = [
        ein,                      # EIN 9
        "01",                     # MFT
        txpd,                     # tax period
        "SYNT",                   # name control
        MOD_NAME.ljust(35),       # name
        "1",                      # FSC
        sic,                      # SIC
        frz,                      # freeze codes
        "2027105", "2027105", "2034105",
        str(assd_cents).zfill(13),   # ASSD
        "0" * 13,                    # DEP
        "0" * 13,                    # CRD
        "0" * 11, "0" * 11, "0" * 11, "0" * 11,
        w8,
        "000",
    ]
    line = "".join(fields)
    assert len(line) == 181, len(line)
    return line


def trn(ein, txpd, tc, dt, amt_cents, cyc="202330", dln="09999900000001"):
    line = (ein + "01" + txpd + tc + dt + str(amt_cents).zfill(13) + cyc + dln)
    assert len(line) == 60, len(line)
    return line


MODULES = [
    # deferral window, penalty smaller than the deferral -> floored at zero
    mod("990000001", "202006", 2000000),
    # deferral window, penalty exactly equal to the deferral
    mod("990000002", "202006", 100000),
    # deferral window, zero assessment -> deferral amount is zero
    mod("990000003", "202009", 0),
    # deposit carrying an impossible julian day
    mod("990000004", "202306", 5000000),
    # deposit dated in a non-leap century year, thousands of days late
    mod("990000005", "202306", 5000000),
    # deposit dated in a leap century year, before the due date
    mod("990000006", "202306", 5000000),
    # deposit whose packed amount carries a negative sign
    mod("990000007", "202306", 5000000),
    # module with no transactions at all
    mod("990000008", "202306", 5000000),
    # deposits whose penalty lands exactly on a half cent at each rate
    mod("990000009", "202306", 5000000),
    # deposit large enough to overflow the penalty and report pictures
    mod("990000010", "202306", 5000000),
]

TRANS = [
    trn("990000001", "202006", "650", "2020254", 100000),
    trn("990000002", "202006", "650", "2020254", 500000),
    trn("990000003", "202009", "650", "2020320", 100000),
    trn("990000004", "202306", "650", "2023400", 100000),
    trn("990000005", "202306", "650", "2100050", 100000),
    trn("990000006", "202306", "650", "2000100", 100000),
    trn("990000007", "202306", "650", "2023300", 100000),
    trn("990000009", "202306", "650", "2023199", 100025),
    trn("990000009", "202306", "650", "2023204", 10010),
    trn("990000009", "202306", "650", "2023236", 100005),
    trn("990000010", "202306", "650", "2023300", 9999999999999),
]

ORPHAN = [trn("000000001", "202306", "650", "2023300", 100000)]


def main(tree):
    with open(tree + "/data/MODMAST.txt") as handle:
        modmast = handle.read().splitlines()
    with open(tree + "/data/TRANIN.txt") as handle:
        tranin = handle.read().splitlines()
    modmast = modmast + MODULES
    tranin = ORPHAN + tranin + TRANS
    with open(tree + "/data/MODMAST.txt", "w") as handle:
        handle.write("\n".join(modmast) + "\n")
    with open(tree + "/data/TRANIN.txt", "w") as handle:
        handle.write("\n".join(tranin) + "\n")
    print("modules %d transactions %d" % (len(modmast), len(tranin)))


if __name__ == "__main__":
    main(sys.argv[1])
