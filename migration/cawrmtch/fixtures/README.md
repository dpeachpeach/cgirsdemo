# CAWRMTCH golden pairs

Each directory is one golden pair captured by running the GnuCOBOL build of
`src/CAWRMTCH.cbl` (step 100):

- `MODOFF.dat` — step input, 150-byte BMFMOD records as `OFFSET` wrote them.
- `CAWRW2.txt` — step input, 44-byte SSA W-2 totals.
- `CAWRMTCH.rpt` — expected output, the report the COBOL wrote.
- `counters.txt` — expected output, the five `DISPLAY` counters.

| Pair | Provenance |
|---|---|
| `shipped` | `data/` fixtures as committed, after `./tools/build.sh && ./run/pipeline.sh` |
| `s1_941only` | synthetic: 941 groups with no W-2 (C004), incl. a zero-liability group and groups after W-2 EOF |
| `s2_multimodule` | synthetic: three MFT 01 periods in one tax year plus an MFT 02 module and a second tax year |
| `s3_dup_w2` | synthetic: two W-2 rows for the same EIN and tax year |
| `s4_tolerance` | synthetic: truncated 1% tolerance, exact boundary, one cent over, $100 floor |
| `s5_overflow` | synthetic: liability wider than the report's edit field |

Synthetic inputs were produced in a scratch copy of the repository by adding
records to `data/MODMAST.txt` and `data/CAWRW2.txt`, re-running `BLDFIX` and the
full pipeline through step 100, and capturing what the COBOL produced. No
expected value in this directory was derived from the IRM or from the rule.
