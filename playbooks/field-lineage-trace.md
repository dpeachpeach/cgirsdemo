Playbook: Copybook Field Lineage Trace — cgirsdemo

## Overview

Given one field from `copybooks/` in `github.com/dpeachpeach/cgirsdemo`, find every program that touches it and determine whether those programs agree on what it means. The copybook declares an offset and a length and says nothing about meaning, so two programs can hold incompatible beliefs about the same bytes with nothing to reconcile them. Findings of this kind are invisible from any single program and contradict no document.

## What's Needed From User

- A field name from `copybooks/` (e.g. `BMF-W8`, `BMF-FRZ`, `BMF-ASED`, `BMF-PFTD`). Group items are acceptable.
- Nothing else.

## Procedure

1. Announce the field, the copybook it lives in, and the four steps below. Announce each step as it starts.
2. Locate the declaration in `copybooks/*.cpy`: level number, `PIC`, `USAGE`, byte length, and byte offset within the record — computed by summing the lengths of all preceding elementary items (`COMP-3` occupies `ceil((digits+1)/2)` bytes; count them correctly, an off-by-one here invalidates the whole trace).
3. Find every program that references the field, directly or through a group item or `REDEFINES`. Search `src/` and `tools/` for the field name, its parent group names, and any subordinate items; include reads via reference modification (`FIELD(1:2)`) and moves of the whole record.
4. For each reference determine two things separately: **which byte positions** are read or written, and **what the program treats those bytes as meaning** — inferred from the surrounding logic (comparisons, tables, arithmetic, branch outcomes), never from the field name or a comment.
5. Compare across programs. Flag any field where two programs assign different meanings to overlapping bytes, or where one program writes bytes another program reads under a different interpretation.
6. Trace the consequence: for each write→read pair, state plainly what changing the writing program does to the reading program, and which output/report the effect surfaces in (see the dataset chain in `docs/PIPELINE.md`).
7. Write the report to `reports/LINEAGE-<FIELD>-<YYYY-MM-DD>.md` (the directory is gitignored — a working artifact, never committed) and print the headline conflict plus the condensed table to the transcript. The transcript is the deliverable; the file is the backup.
8. Validate: re-open every cited `file:line`, confirm the byte positions claimed match the code, and confirm the declared offset+length arithmetic against the copybook and the `RECFM`/`LRECL` in the copybook header and `catlg/LISTCAT.txt`.

## Specifications

- Deliverable: the headline conflict and table printed in the session transcript, backed by `reports/LINEAGE-<FIELD>-<YYYY-MM-DD>.md` on disk (gitignored, not committed).
- Report format:

```markdown
## Field: <NAME> — <n> bytes at offset <n> in <COPYBOOK>

<One sentence: the copybook declares offset and length and says nothing about
meaning, so the programs below can hold incompatible beliefs about these bytes —
followed by whether, here, they do.>

| Program | Positions | Read/Write | Interpreted as | Source |
|---------|-----------|------------|----------------|--------|

### Conflicts
### Downstream consequence
```

- Open the report with the one-sentence statement above — it is the point of the exercise, not a preamble. State the actual outcome for this field in it; a trace that finds no conflict says so.
- Every row sourced as `path:line`. A reader must be able to verify any row in ten seconds.
- The "Interpreted as" column must be justified by logic, not by naming. If the evidence is thin, say "insufficient evidence" rather than guessing.
- Runtime target under six minutes.
- Validation: every cited line re-read; offset arithmetic reconciles to the record length.

## Advice and Pointers

- Fixed format, columns 8–72: anything past column 72 is not compiled and is not logic.
- A program can touch a field without naming it: whole-record `MOVE`s, group-level writes, `REDEFINES` and reference modification all count. A program that reads a record, changes other fields and rewrites it is a pass-through, not a writer of this field — say which it is.
- `COMP-3` sign nibbles and zoned/display differences change what a byte "is". Two programs reading the same byte as display character vs packed digit is exactly the class of conflict being hunted.
- Comments in this corpus are deliberately stale; the field's name is equally unreliable. Meaning comes from what the code does with the bytes.
- The module record is threaded through every step of the pipeline — each program reads the previous generation and writes the next (`docs/PIPELINE.md`), which is what makes write→read consequences traceable.
- Keep the conflict count honest. One well-evidenced conflict with its downstream consequence beats a list of coincidental co-references.

## Forbidden Actions

- Do **not** infer meaning from field names, comments, or the copybook header revision notes.
- Do **not** report two programs merely referencing the same field as a conflict; a conflict requires incompatible interpretations of overlapping bytes.
- Do **not** invent a citation. If no program writes the field, say so explicitly.
- Do **not** look for or use an answer key; none exists in the repository.
- Do **not** modify the corpus, and do **not** commit anything — including the report, which stays gitignored under `reports/`.
