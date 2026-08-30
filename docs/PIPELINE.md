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
their inputs in **EIN / MFT / tax-period** sequence, ascending. `run/pipeline.sh`
satisfies this by generating the fixtures in key order and never sorting.

The JCL satisfies it differently: each merge job carries `SORT` presort steps
(`SRT1`, `SRT2`) that write a passed temporary the program step then reads.
The field specifications live in `ctl/`, not in the JCL:

| Card | Sequences | Read by |
|---|---|---|
| `ENTSRT` | entity master, EIN | `ENTVAL` |
| `MODSRT` | module master, EIN / MFT / tax period | `DUPCHK`, `FTDCALC`, `PENCALC`, `CAWRMTCH` |
| `TRNSRT` | transaction file, EIN / MFT / tax period / TC | `DUPCHK`, `FTDCALC`, `PENCALC` |
| `W2SRT` | SSA W-2 totals, EIN / tax year | `CAWRMTCH` |

Displacements in the cards are one-relative into the record as `copybooks/`
lays it out. Nothing checks that a card and the program reading its output
agree about key composition or direction; that agreement is maintained by hand.

`CAWRMTCH` additionally performs a control break, summing every MFT 01 module
for an EIN and tax year before comparing against the SSA W-2 totals. It is the
only step in the corpus with three-way merge logic (matched / W-2 only /
941 only), and the only one whose two inputs are sequenced on different keys.

Substituting VSAM KSDS would remove the requirement, and the presort steps
with it.

## Dataset naming

The JCL uses GDG generations (`TAX.BMF.MODULE.STAT(+1)` writing, `(0)` reading)
so a restart at any step picks up the prior generation. `run/pipeline.sh` uses
flat filenames in `data/` instead, since there are no generation groups
off-mainframe.

The bases are defined by `jcl/DEFGDG.jcl` and the non-generation datasets by
`jcl/BMFALOC.jcl`, both one-time setup jobs. `catlg/LISTCAT.txt` is an IDCAMS
listing of the resulting inventory — fourteen GDG bases and their retained
generations. Reject datasets (`TAX.BMF.ENTVAL.REJECTS`,
`TAX.BMF.DUPCHK.REJECTS`) are generation groups with `LIMIT(30)` rather than
the `LIMIT(5)` the module generations carry, so a reject can be researched a
month after the cycle that produced it.

## Run order

`sched/BMFNITE.ca7` holds the job dependency graph as the scheduler sees it:
one `LJOB` listing per job, with predecessor and dataset-creation requirements
and the jobs each completion triggers. It is the fourth statement of the same
ordering — after the COBOL's read/write chain, `jcl/BMFNITE.jcl`, and the table
above — and the only one that says anything about concurrency: `BMF100` and
`BMF110` both wait on `BMF090` and may run at the same time.
