"""Append synthetic MODMAST.txt records that reach OVPINT branches the
shipped fixtures never touch.  Run in the scratch tree only."""

FIELDS = [
    ("EIN", 9), ("MFT", 2), ("TXPD", 6), ("NCTL", 4), ("NAME", 35),
    ("FSC", 1), ("SIC", 1), ("FRZ", 8), ("ASED", 7), ("RSED", 7),
    ("CSED", 7), ("ASSD", 13), ("DEP", 13), ("CRD", 13), ("PFTD", 11),
    ("PFTF", 11), ("PFTP", 11), ("INT", 11), ("W8", 8), ("TCCNT", 3),
]


def money(amount, digits):
    cents = int(round(amount * 100))
    return str(cents).rjust(digits, "0")


def line(ein, mft, txpd, name, dep, crd=0.0, assd=0.0):
    values = {
        "EIN": ein, "MFT": mft, "TXPD": txpd, "NCTL": "SYNT",
        "NAME": name.ljust(35)[:35], "FSC": "1", "SIC": "0",
        "FRZ": " " * 8, "ASED": "2030105", "RSED": "2030105",
        "CSED": "2037105", "ASSD": money(assd, 13), "DEP": money(dep, 13),
        "CRD": money(crd, 13), "PFTD": "0" * 11, "PFTF": "0" * 11,
        "PFTP": "0" * 11, "INT": "0" * 11, "W8": "SYNTH000", "TCCNT": "000",
    }
    out = "".join(values[n].ljust(w)[:w] for n, w in FIELDS)
    assert len(out) == 181, len(out)
    return out


SYNTH = [
    # year 2100 availability: DATCNV 3000-LEAP mod-100 non-leap branch, and a
    # cycle date earlier than the availability date (negative day count).
    line("990000001", "01", "209912", "SYNTH CENTURY NON LEAP", 5000.00),
    # year 2000 availability: 3000-LEAP mod-400 leap branch.
    line("990000002", "01", "199912", "SYNTH CENTURY LEAP", 5000.00),
    # tax-period month 99: ADD 1 TO XM overflows PIC 9(2) to 00, so DATCNV
    # rejects the availability date (RC 8).
    line("990000003", "01", "202499", "SYNTH BAD MONTH", 5000.00),
    # overpayment wider than OR-OVP PIC ZZZZZZZZ9.99.
    line("990000004", "01", "202303", "SYNTH WIDE OVERPAYMENT", 99999999999.99),
    # one-cent overpayment: interest rounds to zero.
    line("990000005", "01", "202303", "SYNTH ONE CENT", 0.01),
    # 91.25 over 1186 days at 7 percent is exactly 20.755 before ROUNDED.
    line("990000006", "01", "202303", "SYNTH HALF UP", 91.25),
    # deposits exactly equal the liability: overpayment zero, no report line.
    line("990000007", "01", "202303", "SYNTH ZERO OVERPAYMENT", 100.00,
         assd=100.00),
]

with open("data/MODMAST.txt", "r") as handle:
    body = handle.read()
if "990000001" not in body:
    with open("data/MODMAST.txt", "a") as handle:
        for record in SYNTH:
            handle.write(record + "\n")
print("appended", len(SYNTH))
