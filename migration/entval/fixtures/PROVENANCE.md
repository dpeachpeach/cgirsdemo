# ENTVAL fixture provenance

Every expectation in `../tests/` comes from one of the captures here, and every
capture is the literal output of the COBOL program, not a value derived from
IRM 3.13.2 or from the rule as understood by anyone.

Capture environment: GnuCOBOL 3.1.2, fixed format, built by `./tools/build.sh`
with the shipped flags (`cobc -x -std=ibm -I copybooks/`). `ENTVAL` calls the
COBOL shim `src/NAMCTL.cbl`; the HLASM under `src/asm/` does not execute.

| File | What it is | How it was produced |
|---|---|---|
| `golden_shipped_input.txt` | the 52 shipped entity records, `data/ENTMAST.txt` verbatim | copied from the repository |
| `golden_shipped_output.txt` | `data/ENTVAL.dat`, split into 150-byte records | `./tools/build.sh && bin/BLDFIX && bin/ENTVAL` |
| `golden_shipped_enterr.rpt` | `data/ENTERR.rpt` verbatim | same run |
| `golden_shipped_counters.json` | the four 9000-EOJ `DISPLAY` counters | same run, parsed from stdout |
| `synthetic_cases.json` | 20 single-record inputs built to reach branches the shipped fixtures never execute, each with the record `ENTVAL` wrote, the report lines it wrote and its counters | for each case: write the record to `data/ENTMAST.txt` in a scratch clone, run `bin/BLDFIX` then `bin/ENTVAL`, capture all three outputs |
| `golden_open_failure.json` | return code and stdout of `bin/ENTVAL` with `data/ENTMAST.dat` absent | delete the input in the scratch clone and run the step |

The synthetic records were written and run only inside a scratch clone of the
repository; `data/` on this branch is untouched.
