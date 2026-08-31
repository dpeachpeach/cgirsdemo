# FTDCALC fixture provenance

Every file here is a capture of an actual GnuCOBOL 3.1.2 run of `src/FTDCALC.cbl`,
built with `./tools/build.sh` (fixed format, `-std=ibm`, unmodified flags).
Nothing here was hand-computed. `counters.txt` is the program's own DISPLAY output.

| Directory | Inputs | How it was produced |
|---|---|---|
| `shipped/` | `MODSTAT.dat`, `TRANIN.dat` | `./tools/build.sh && ./run/pipeline.sh` on a clean checkout; `MODSTAT.dat` is what step 030 `STATCALC` handed to step 040, `MODFTD.dat` and `FTDCALC.rpt` are what step 040 wrote. |
| `synthetic/` | `MODSTAT.dat`, `TRANIN.dat` | Scratch clone of the repo with `make-synthetic-fixtures.py` appending eight modules and seven transactions to `data/MODMAST.txt` and `data/TRANIN.txt`, then `bin/BLDFIX && bin/DUPCHK && bin/STATCALC && bin/FTDCALC`. Targets the branches the shipped fixtures never reach. |
| `synthetic-negative/` | `synthetic/MODSTAT.dat`, `TRANIN.dat` | The synthetic `TRANIN.dat` with the COMP-3 sign nibble of one TC 650 amount flipped from `C` to `D`, then `bin/FTDCALC`. A negative deposit amount cannot be expressed in `data/TRANIN.txt`, whose `TT-AMT` is unsigned `PIC 9(11)V99`, so this is the only way to reach the `PA-BAS < ZERO` path in `PENACC`. |

The scratch tree was discarded; `make-synthetic-fixtures.py` is kept so the
synthetic capture can be reproduced. It is a generator, not part of the suite.
