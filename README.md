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
jcl/         decorative JCL, one member per step, plus driver and catalogued proc
data/        synthetic fixtures (text source; *.dat are built, gitignored)
run/         pipeline.sh — the real orchestration
tools/       BLDFIX card-to-tape loader, collint.sh column-72 lint
docs/        PIPELINE.md — step sequence and dataset flow
```

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

**The JCL does not execute.** It is decorative: plausible DD names, GDG
generations, `DISP`, `COND=(4,LT)`, a catalogued procedure. Real orchestration
lives in `run/pipeline.sh`. See `docs/PIPELINE.md`.

**No VSAM.** Real master files would be indexed (KSDS). Everything here is
`ORGANIZATION SEQUENTIAL`, because GnuCOBOL's ISAM support requires BDB or
VBISAM compiled in and frequently is not. Match/merge steps therefore require
their inputs in key sequence, which the fixtures satisfy.

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
findable only by tracing a field across a program boundary. The answer key is
held privately and is not in this repository.
