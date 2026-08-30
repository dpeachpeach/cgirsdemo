# Pipeline — step sequence and dataset flow

The nightly cycle is twelve steps. `run/pipeline.sh` is the real orchestration;
`jcl/BMFNITE.jcl` is the decorative equivalent and does not execute.

## Step sequence

| Step | Program | IRM | Reads | Writes |
|---|---|---|---|---|
| 000 | `BLDFIX` | — | `MODMAST.txt`, `ENTMAST.txt`, `TRANIN.txt` | `BMFMOD.dat`, `ENTMAST.dat`, `TRANIN.dat` |
| 010 | `ENTVAL` | 3.13.2 | `ENTMAST.dat` | `ENTVAL.dat`, `ENTERR.rpt` |
| 020 | `DUPCHK` | 21.7.9 | `BMFMOD.dat`, `TRANIN.dat` | `MODDUP.dat`, `DUPCHK.rpt` |
| 030 | `STATCALC` | 25.6.1 | `MODDUP.dat` | `MODSTAT.dat`, `STATCALC.rpt` |
| 040 | `FTDCALC` | 20.1.4 | `MODSTAT.dat`, `TRANIN.dat` | `MODFTD.dat`, `FTDCALC.rpt` |
| 050 | `PENCALC` | 20.1.2 | `MODFTD.dat`, `TRANIN.dat` | `MODPEN.dat`, `PENCALC.rpt` |
| 060 | `ESTPEN` | 20.1.3 | `MODPEN.dat` | `MODEST.dat`, `ESTPEN.rpt` |
| 070 | `FRZEVAL` | 21.5.6 | `MODEST.dat` | `MODFRZ.dat`, `FRZEVAL.rpt` |
| 080 | `OVPINT` | 20.2.4 | `MODFRZ.dat` | `MODINT.dat`, `OVPINT.rpt` |
| 090 | `OFFSET` | 21.4.6 | `MODINT.dat`, `DEBTS.txt` | `MODOFF.dat`, `OFFSET.rpt` |
| 100 | `CAWRMTCH` | — | `MODOFF.dat`, `CAWRW2.txt` | `CAWRMTCH.rpt` |
| 110 | `NOTGEN` | — | `MODOFF.dat` | `NOTICE.dat`, `NOTGEN.rpt` |

The module record is threaded through every step: each program reads the
previous generation, updates fields, and writes the next. That chain is what
makes cross-program field tracing possible.

## Called subprograms

| Called | By | Reference source |
|---|---|---|
| `NAMCTL` | `ENTVAL` | `src/asm/NAMCTL.asm` (48-byte parm) |
| `DATCNV` | `STATCALC`, `FTDCALC`, `PENCALC`, `DATECNV` | `src/asm/DATCNV.asm` (24-byte parm) |
| `PENACC` | `FTDCALC` | `src/asm/PENACC.asm` (32-byte parm) |
| `DATECNV` | `OVPINT`, `NOTGEN` | COBOL only — IRC 7503 business-day shift |

Each parm area is a flat block mapped by displacement. The HLASM `DSECT`s and
the COBOL `LINKAGE SECTION` declarations must agree byte for byte; the sizes
above are the contract.

## Sequencing requirement

`DUPCHK`, `FTDCALC`, `PENCALC` and `CAWRMTCH` are match/merge steps and require
their inputs in **EIN / MFT / tax-period** sequence. There is no sort step —
the fixtures are generated in key order. On a real system a `SORT` would
precede each merge; substituting VSAM KSDS would remove the requirement
entirely.

`CAWRMTCH` additionally performs a control break, summing every MFT 01 module
for an EIN and tax year before comparing against the SSA W-2 totals. It is the
only step in the corpus with three-way merge logic (matched / W-2 only /
941 only).

## Dataset naming

The JCL uses GDG generations (`TAX.BMF.MODULE.STAT(+1)` writing, `(0)` reading)
so a restart at any step picks up the prior generation. `run/pipeline.sh` uses
flat filenames in `data/` instead, since there are no generation groups
off-mainframe.
