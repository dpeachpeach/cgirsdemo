# STATCALC golden captures

Every byte here came out of the GnuCOBOL 3.1.2 build of `src/STATCALC.cbl`
(`./tools/build.sh`, then `run/pipeline.sh` through step 030).  No expected
value in the test suite is derived from the IRM, the comments, or the rule.

| File | Provenance |
|---|---|
| `shipped_moddup.dat` | `data/MODDUP.dat` — input to step 030 on a clean checkout |
| `shipped_modstat.dat` | `data/MODSTAT.dat` — what the COBOL wrote for that input |
| `shipped_statcalc.rpt` | `data/STATCALC.rpt` for the same run |
| `shipped_totals.txt` | stdout of `bin/STATCALC` for the same run |
| `synthetic_modmast_records.txt` | the ten fixture records appended to `data/MODMAST.txt` in a scratch clone to reach uncovered branches |
| `synthetic_moddup.dat` | `data/MODDUP.dat` in the scratch clone after `BLDFIX` + `DUPCHK` |
| `synthetic_modstat.dat` | `data/MODSTAT.dat` the COBOL wrote in the scratch clone |
| `synthetic_statcalc.rpt` | `data/STATCALC.rpt` from the scratch clone |
| `synthetic_totals.txt` | stdout of `bin/STATCALC` in the scratch clone |

The scratch clone lives outside the repository; only these captures are kept.
