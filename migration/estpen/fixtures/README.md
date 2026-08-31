# ESTPEN golden fixtures

Every file here was captured from GnuCOBOL 3.1.2 running `bin/ESTPEN` built by
`./tools/build.sh`. They are the oracle: expected values come from the COBOL,
never from IRM 20.1.3 or from the rule as anyone understands it.

`.dat.hex` files are the hex dump of a 150-byte-record sequential file
(`xxd -p`), so the packed-decimal (COMP-3) bytes survive in a text-safe form.

| Golden pair | Input | Provenance |
|---|---|---|
| `shipped` | `MODPEN-shipped.dat.hex` (52 records) | `./tools/build.sh && ./run/pipeline.sh` on a pristine checkout |
| `synthpipe` | `MODPEN-synthpipe.dat.hex` (62 records) | same, after appending ten synthetic records to `data/MODMAST.txt` in a scratch clone and re-running `BLDFIX` and steps 010–060 |
| `direct` | `MODPEN-direct.dat.hex` (7 records) | `bin/ESTPEN` run against a hand-packed `data/MODPEN.dat` in a scratch clone; needed for values `MODMAST.txt` cannot express, since its `TM-ASSD`/`TM-DEP`/`TM-PFTP` are unsigned `PIC 9(n)V99` |

Counters are the `DISPLAY` lines ESTPEN writes at end of job:

| Golden pair | READ | WRITTEN | ASSESSED |
|---|---|---|---|
| `shipped` | 52 | 52 | 1 |
| `synthpipe` | 62 | 62 | 7 |
| `direct` | 7 | 7 | 5 |
