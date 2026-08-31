"""Append synthetic fixture records (scratch tree only) for uncovered branches."""


def mod(ein, txpd, name, sic="0", frz=" " * 8, assd="0", w8="12B02269"):
    assd_cents = f"{int(round(float(assd) * 100)):013d}"
    line = (
        f"{ein}01{txpd}"
        + "SYNT"
        + f"{name:<35}"
        + "1"
        + sic
        + frz
        + "2027105"
        + "2027105"
        + "2034105"
        + assd_cents
        + "0" * 13
        + "0" * 13
        + "0" * 11 * 4
        + w8
        + "000"
    )
    assert len(line) == 181, len(line)
    return line


def trn(ein, txpd, tc, dt, amt, cyc="202030", dln="90221000000000"):
    amt_cents = f"{int(round(float(amt) * 100)):013d}"
    line = f"{ein}01{txpd}{tc:03d}{dt:07d}{amt_cents}{cyc}{dln}"
    assert len(line) == 60, len(line)
    return line


mods = [
    mod("990001001", "202006", "DEFERRAL WIPES OUT PENALTY", assd="50000.00"),
    mod("990001002", "202009", "DEFERRAL LEAVES PENALTY", assd="2000.00"),
    mod("990001003", "202012", "DEFERRAL ZERO ASSESSMENT", assd="0"),
    mod("990001004", "202306", "NO TRANSACTIONS AT ALL", assd="80000.00"),
    mod("990001005", "202306", "BAD JULIAN DEPOSIT DATE", assd="80000.00"),
    mod("990001006", "202306", "DELINQUENCY OVER 9999 DAYS", assd="5000.00"),
    mod("990001007", "202306", "PENALTY OVER 8 REPORT DIGITS", assd="9999999.99"),
    mod("990001008", "202306", "PENALTY OVERFLOWS PA-AMT", assd="9999999.99"),
]

trns = [
    trn("990001001", "202006", 650, 2020240, "40000.00"),
    trn("990001002", "202009", 650, 2020330, "100000.00"),
    trn("990001004", "209912", 650, 2023200, "500.00"),
    trn("990001005", "202306", 650, 2023400, "70000.00"),
    trn("990001006", "202306", 650, 2099200, "1000.00"),
    trn("990001007", "202306", 650, 2023240, "1500000000.00"),
    trn("990001008", "202306", 650, 2023240, "20000000000.00"),
]

with open("data/MODMAST.txt", "a") as fh:
    for line in mods:
        fh.write(line + "\n")
with open("data/TRANIN.txt", "a") as fh:
    for line in trns:
        fh.write(line + "\n")
print("appended", len(mods), "modules and", len(trns), "transactions")
