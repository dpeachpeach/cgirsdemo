Playbook: Port and Characterize a COBOL Program — cgirsdemo

## Overview

Port one COBOL program in `github.com/dpeachpeach/cgirsdemo` to Python and produce a characterization suite that proves equivalence with the legacy program. **The COBOL is the specification** — not the IRM, not what the rule ought to be. Expected output is always what the legacy program actually produced for a given input. If the code has a bug, the port reproduces the bug and the test asserts it; correctness improvements are a separate, deliberate change with their own approval, because folding them into a migration destroys the only verification mechanism available.

## What's Needed From User

- A program name from `src/` (e.g. `FTDCALC`, `PENCALC`, `STATCALC`, `ESTPEN`, `OVPINT`, `OFFSET`, `FRZEVAL`, `DUPCHK`, `ENTVAL`).
- Nothing else. GnuCOBOL is installed by the playbook if missing.

## Procedure

1. Announce the program and the seven steps below; announce each step as it starts and print the coverage number as soon as Step 3 produces it.
2. **Establish the oracle.** Ensure GnuCOBOL is present (`cobc --version`; if absent `sudo apt-get install -y gnucobol`, developed against 3.2.0, 3.1.2 also works). Run `./tools/build.sh` then `./run/pipeline.sh`. Capture the target step's inputs and outputs — the module record generation it reads, the one it writes, and its `data/<PROGRAM>.rpt`. These pairs are golden and are ground truth by definition.
3. **Enumerate branches.** Every conditional path in `src/<PROGRAM>.cbl`: `IF`/`ELSE`, level-88 conditions, `EVALUATE` branches, `PERFORM ... UNTIL` exits, file-status paths, and branches inside any subprogram it `CALL`s. Number them; this list is the denominator for coverage.
4. **Measure coverage.** Determine which enumerated branches the shipped fixtures in `data/` actually execute — instrument by reasoning over the fixture records, or by building an instrumented copy of the program in a scratch tree. Report the gap explicitly as a headline number, not a footnote.
5. **Construct targeted inputs for uncovered branches.** Work in a scratch copy of the repo (the programs open hard-coded relative paths under `data/`). Add fixture records to the relevant `data/*.txt` that satisfy each uncovered branch's precondition, re-run `BLDFIX` and the pipeline steps up to and including the target, and **capture the COBOL's output as the expected value.** Never derive an expected value from the rule.
6. **Write characterization tests.** One per golden pair, under `port/<program>/tests/`, runnable with `pytest`. Assert current behavior including defects. Name tests honestly — `test_minimum_penalty_uses_stale_hardcoded_amount` is a good name, because the name is where the drift gets recorded.
7. **Write the Python implementation** at `port/<program>/<program>.py`, matching COBOL arithmetic semantics: `Decimal` never `float`; explicit rounding matching `ROUNDED` (and truncation where there is no `ROUNDED`); packed-decimal (`COMP-3`) sign handling; fixed-width field truncation and zero-fill; the same record layout offsets as the copybook.
8. **Converge.** Run the suite against both implementations. Classify each mismatch: *new code wrong* → fix the Python and iterate; *legacy has a bug* → **implement the bug**, and log it separately as a proposed fix; *both defensible* → stop and log an Acceptable Difference candidate for human decision.
9. Write the report to `reports/PORT-<PROGRAM>-<YYYY-MM-DD>.md` (gitignored — a working artifact, never committed) and print the headline numbers and both tables to the transcript. Only `port/` is added to the repo; scratch-tree changes stay out.

## Specifications

- Deliverables: `port/<program>/<program>.py` and `port/<program>/tests/` in the repo; the report is printed to the transcript and kept on disk at `reports/PORT-<PROGRAM>-<YYYY-MM-DD>.md` (gitignored, not committed).
- Report format:

```markdown
## <PROGRAM> — port and characterization

Branches enumerated: N
Branches exercised by shipped fixtures: N (N%)
Synthetic inputs constructed: N
Tests generated: N — all passing against both implementations

### Mismatches encountered and resolved
| # | Symptom | Bucket | Resolution |

### Proposed fixes (NOT applied)
### Acceptable Difference candidates (human decision required)
```

- Success criterion: every generated test passes against the COBOL and against the Python, and the counts in the report are reproducible by re-running `pytest`.
- Validation: run the full suite one final time against both implementations and paste the command and the pass count into the report.
- Runtime target under six minutes per program. Step 5 is the expensive step — if the uncovered-branch count is large, cover the branches with distinct outcomes first and state in the report which were deferred and why.

## Advice and Pointers

- Fixed format, columns 8–72; anything past column 72 is not compiled. Do not pass `-free`.
- The HLASM under `src/asm/` does not execute. The runnable pipeline calls COBOL shims of the same names (`src/NAMCTL.cbl`, `src/DATCNV.cbl`, `src/PENACC.cbl`); port against the shims and say so out loud in any demo.
- The JCL, sort cards, CA-7 definitions and catalog listing are decorative. `run/pipeline.sh` is the real orchestration; `docs/PIPELINE.md` documents the step order and dataset flow.
- `.dat` files are built artifacts (gitignored) produced from the `.txt` fixtures by `tools/BLDFIX.cbl`; regenerate them rather than editing them.
- Comments in this corpus are deliberately stale. They are not the specification either — the compiled code is.
- Rounding is where ports usually diverge first: COBOL `COMPUTE` with `ROUNDED` is half-up on the target's scale, and intermediate truncation into a smaller `PIC` happens at each `MOVE`. Reproduce the intermediate widths, not just the final one.

## Forbidden Actions

- Do **not** fix a legacy bug in the port. Implement it, assert it in a test, and log the proposed fix separately.
- Do **not** derive an expected value from the IRM or from the rule as you understand it. Expected values come from running the COBOL.
- Do **not** silently resolve a mismatch where both implementations are defensible — that is a policy decision and belongs to a human. Log it as an Acceptable Difference candidate.
- Do **not** edit `src/`, `copybooks/`, or the shipped fixtures in the deliverable branch; synthetic fixtures live in the scratch tree and, if they need to persist, under `port/<program>/fixtures/`.
- Do **not** switch the build to free format or change `tools/build.sh` flags to make something compile.
