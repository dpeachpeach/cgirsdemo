# irs-masterfile-demo

A **synthetic** COBOL corpus modelling a mini Business Master File / Individual
Master File batch pipeline, built for an agentic code-comprehension walkthrough.
Twelve programs, each paired with the real, published IRM section it implements.

## What this is not

**This is not IRS code.** No line of it came from the IRS, and it must never be
represented as such. It is an original synthetic corpus written to *resemble*
1980s federal batch COBOL in shape, idiom and structure.

**There is no taxpayer data here.** Every EIN, name, address and dollar amount
in `data/` is generated. Entity names follow the bird-and-plant convention the
IRM itself uses in its worked examples (Cardinal, Warbler, Osprey, Zinnia).

The **IRM markdown under `irm/` is real** — harvested from irs.gov, with the
source URL and retrieval date in each file's front matter. That is the point:
the code is synthetic, the specification it is measured against is genuine.

## Layout

```
irm/         nine IRM sections, harvested from irs.gov, subsection numbers preserved
copybooks/   five copybooks — the shared record contracts
src/         twelve COBOL programs + three COBOL call shims
src/asm/     three HLASM routines (reference source, not executed — see below)
jcl/         decorative JCL, one member per step, plus driver, proc and setup jobs
ctl/         DFSORT control cards read by the presort steps in jcl/
sched/       CA-7 job definitions — the run order as the scheduler holds it
catlg/       LISTCAT.txt — an IDCAMS catalog listing of the dataset inventory
data/        synthetic fixtures (text source; *.dat are built, gitignored)
run/         pipeline.sh — the real orchestration
tools/       BLDFIX card-to-tape loader, collint.sh column-72 lint
docs/        PIPELINE.md — step sequence and dataset flow
```

The same pipeline is described in five notations that have to agree with each
other: the COBOL, the JCL, the sort control cards, the CA-7 definitions and
`docs/PIPELINE.md`. Nothing enforces that agreement.

## Inventory

### Batch components

| Job | JCL member | Program | Function | IRM |
|:---|:---|:---|:---|:---|
| BMFGDG | `DEFGDG` | IDCAMS | Define GDG bases | — |
| BMFALOC | `BMFALOC` | IDCAMS / IEBGENER | Allocate flat files, prime module master | — |
| BMF010 | `ENTVAL` | `ENTVAL` | Entity validation and name control | 3.13.2 |
| BMF020 | `DUPCHK` | `DUPCHK` | Duplicate filing condition | 21.7.9 |
| BMF030 | `STATCALC` | `STATCALC` | Statute date computation (ASED/RSED/CSED) | 25.6.1 |
| BMF040 | `FTDCALC` | `FTDCALC` | Failure to deposit penalty | 20.1.4 |
| BMF050 | `PENCALC` | `PENCALC` | Failure to file / failure to pay | 20.1.2 |
| BMF060 | `ESTPEN` | `ESTPEN` | Corporate estimated tax penalty | 20.1.3 |
| BMF070 | `FRZEVAL` | `FRZEVAL` | Freeze condition evaluation | 21.5.6 |
| BMF080 | `OVPINT` | `OVPINT` | Overpayment interest | 20.2.4 |
| BMF090 | `OFFSET` | `OFFSET` | Refund offset against FMS debts | 21.4.6 |
| BMF100 | `CAWRMTCH` | `CAWRMTCH` | Combined annual wage reporting match | — |
| BMF110 | `NOTGEN` | `NOTGEN` | Notice selection and generation | — |

`BLDFIX` (`tools/`) is the card-to-tape loader that converts the text fixtures
to packed-decimal `.dat` files. It has no JCL member; on a real system the
`.dat` files would arrive from upstream.

### Called subprograms

| Called | Called by | Reference source | Parm |
|:---|:---|:---|:---|
| `NAMCTL` | `ENTVAL` | `src/asm/NAMCTL.asm` | 48 bytes |
| `DATCNV` | `STATCALC`, `FTDCALC`, `PENCALC`, `DATECNV` | `src/asm/DATCNV.asm` | 24 bytes |
| `PENACC` | `FTDCALC` | `src/asm/PENACC.asm` | 32 bytes |
| `DATECNV` | `OVPINT`, `NOTGEN` | COBOL only | — |

### Sort control cards

| Member | Used by | Key |
|:---|:---|:---|
| `ENTSRT` | BMF010 | EIN |
| `MODSRT` | BMF020, BMF040, BMF050, BMF100 | EIN / MFT / tax period |
| `TRNSRT` | BMF020, BMF040, BMF050 | EIN / MFT / tax period / transaction code |
| `W2SRT` | BMF100 | EIN / tax year |

## Building

Requires GnuCOBOL (developed against 3.2.0).

```sh
brew install gnucobol        # or: sudo apt install gnucobol
./tools/build.sh             # compiles everything into bin/
./run/pipeline.sh            # runs the twelve steps end to end
```

Fixed-format source throughout — do **not** pass `-free`. Column discipline is
part of what this corpus demonstrates; `tools/collint.sh` enforces the 72-column
limit.

## Honest limitations

These are deliberate simplifications, stated plainly rather than papered over.

**The assembler does not execute.** `src/asm/` is representative HLASM —
standard OS linkage, `USING`/`DROP`, and a `DSECT` mapping each parameter area
by displacement. GnuCOBOL cannot assemble it and standing up z390 or Hercules
was out of scope. **The runnable pipeline calls COBOL shims of the same names**
(`src/NAMCTL.cbl`, `src/DATCNV.cbl`, `src/PENACC.cbl`), which reproduce the
assembler's behaviour. The `.asm` files are reference source. Say this out loud
in any demo — claiming it runs when it does not is the one thing here that
would actually cost credibility.

**The JCL does not execute**, and neither do the sort cards, the CA-7
definitions or the catalog listing. All of it is decorative: plausible DD
names, GDG generations, `DISP`, `COND=(4,LT)`, a catalogued procedure, DFSORT
field specifications, scheduler requirement lists. Real orchestration lives in
`run/pipeline.sh`, which reads flat files from `data/` in a fixed order. See
`docs/PIPELINE.md`.

Decorative does not mean arbitrary. Each of those artifacts is internally
consistent and consistent with the record layouts in `copybooks/`, so it can be
read against the COBOL and be either right or wrong. That is the whole reason
it is here.

**No VSAM.** Real master files would be indexed (KSDS). Everything here is
`ORGANIZATION SEQUENTIAL`, because GnuCOBOL's ISAM support requires BDB or
VBISAM compiled in and frequently is not. Match/merge steps therefore require
their inputs in key sequence. `run/pipeline.sh` satisfies that by generating
the fixtures in key order; the JCL satisfies it with a presort step ahead of
each merge, driven by the control cards in `ctl/`.

**Not tax-accurate beyond what the IRM states.** Rates, thresholds and statute
rules are taken from the harvested sections; anything outside them is invented
to make the pipeline run.

**Redactions are preserved, not filled in.** Several IRM sections contain runs
of `≡` marking official-use-only content removed before publication (IRM 20.1.4
alone has over 5,000 such characters). These appear in the markdown as
`> REDACTED IN SOURCE` blockquotes so the gap stays visible.

## The point of the exercise

The code is uncommented, cryptically named and globally scoped, the way the
real thing is. Where comments survive they are mostly **stale** — they cite
rates, form revisions and IRM subsections that have since moved. `BMF-W8` is an
eight-byte field read by two programs for two unrelated purposes: `STATCALC`
takes positions 1–2 as a statute condition code, `FTDCALC` takes position 3 as
a ROFTL indicator. Offset without semantics, which is the copybook problem in
miniature.

Deliberate discrepancies exist between the IRM text and the code. At least one
is invisible from any single program and contradicts no document at all — it is
findable only by tracing a field across a program boundary. Another is not a
COBOL defect at all: it is a disagreement between a job's control cards and the
program that job runs, visible only if you read both. The answer key is held
privately and is not in this repository.
