Playbook: IRM / Code Reconciliation — cgirsdemo

## Overview

Given one batch program in `github.com/dpeachpeach/cgirsdemo`, produce the delta between what the published IRM says and what the COBOL actually does, plus any disagreement between the program and the four adjacent notations that describe the same job (JCL, DFSORT control cards, CA-7, `docs/PIPELINE.md`, `catlg/LISTCAT.txt`). The run is performed live in front of an audience: every row must be sourced to a file and line or an IRM subsection, and be defensible under questioning.

## What's Needed From User

- A program name, one of: `ENTVAL`, `DUPCHK`, `STATCALC`, `FTDCALC`, `PENCALC`, `ESTPEN`, `FRZEVAL`, `OVPINT`, `OFFSET`.
- Nothing else. The program → IRM section → JCL member mapping is the inventory table in `README.md`.

## Procedure

1. Announce the run: program, the IRM section it maps to per the README inventory table, and the four steps below. Repeat a one-line announcement at the start of every step — a silent stretch reads as a hang.
2. Read `README.md` (layout, deliberate discrepancies, honest limitations) and the copybooks the program `COPY`s, from `copybooks/`. Do **not** open `irm/` yet.
3. **Step 1 — extract rules from the code, with the IRM unread.** This ordering is mandatory. Enumerate every branch, level-88 condition, `EVALUATE` branch, threshold, rate and literal in `src/<PROGRAM>.cbl` and in any subprogram it `CALL`s. Write each as one normalized *condition → outcome* statement with `file:line`. Record them in the report before opening `irm/`.
4. **Step 2 — extract rules from the IRM.** Read the mapped section under `irm/` and extract rules in the same normalized form, keyed by subsection number. Note every `> REDACTED IN SOURCE` span and which subsections it covers.
5. **Step 3 — diff.** Place every rule from either side in exactly one bucket: `MATCH` (both, same behavior), `DRIFT` (both, behavior differs), `CODE-ONLY` (in code, no IRM subsection), `IRM-ONLY` (in IRM, not implemented), `UNVERIFIABLE` (rule falls inside a redacted span).
6. **Step 4 — check the adjacent notations.** For this program's job read `jcl/<MEMBER>.jcl` (DD names, `DISP`, `COND`, GDG generations), the `ctl/*.ctl` cards for any presort feeding it, `sched/BMFNITE.ca7` (run order, requirements), `docs/PIPELINE.md` (dataset flow) and `catlg/LISTCAT.txt` (dataset inventory, RECFM/LRECL). Compare sort key fields, record lengths, dataset names and step ordering hardest. Report each disagreement as `CROSS-NOTATION`.
7. Write the report to `reports/RECON-<PROGRAM>-<YYYY-MM-DD>.md` (the directory is gitignored — the report is a working artifact, never committed) and print the headline finding plus the condensed table to the session transcript. The transcript is the deliverable; the file is the backup.
8. Validate before delivering: open each cited `file:line` and confirm it says what the row claims; confirm no row cites a subsection inside a redacted span as `DRIFT`; confirm every rule is in exactly one bucket and the summary counts add up.

## Specifications

- Deliverable: the headline finding and table printed in the session transcript, backed by `reports/RECON-<PROGRAM>-<YYYY-MM-DD>.md` on disk (gitignored, not committed).
- Report format:

```markdown
## <PROGRAM> — IRM <section> reconciliation

**Headline:** <highest-severity finding, one sentence>

| # | Rule | IRM says | Code does | Class | Source |
|---|------|----------|-----------|-------|--------|

### Cross-notation findings
### Stale comments (comment contradicts the code it sits on)
### Unverifiable (redacted in source)
### Summary: N match, N drift, N code-only, N irm-only, N unverifiable
```

- Lead with the highest-severity finding, not the first one found. Severity order: `CROSS-NOTATION` > `CODE-ONLY` > `DRIFT` > `IRM-ONLY`.
- In the cross-notation section, state explicitly: *a finding here is not a code defect — the program can be correct and the control cards correct and the pair still wrong.*
- Every claim carries a source: `path:line` for code, JCL, control cards and CA-7; subsection number for IRM. A reader must be able to verify any row in ten seconds.
- Tables over prose. Any section longer than a short paragraph becomes a table.
- Runtime target under six minutes for the program. If the IRM section is large, scope Step 2 to the subsections the code plausibly touches and say in the report that you did.
- Validation: each cited line re-read and confirmed; bucket counts reconcile with the row count.

## Advice and Pointers

- COBOL here is fixed format, columns 8–72. Anything past column 72 is not compiled and must not be read as logic (`tools/collint.sh` is the lint that enforces this).
- Resolve `COPY` members from `copybooks/`. Follow `PERFORM ... THRU` ranges to their exit paragraphs before concluding what a branch does.
- `COMP-3` is packed decimal — sign and rounding behavior are part of the rule, not an implementation detail. `ROUNDED` vs truncation is reportable.
- Level-88 condition names are branch conditions; enumerate them individually.
- Comments in this corpus are deliberately stale: they cite rates, form revisions and IRM subsections that have since moved. Read behavior from the code only. A comment is never a rule, so a comment contradicting the code it sits on never creates or changes a reconciliation row — the row reflects the code, and the contradiction is reported separately under **Stale comments**.
- The IRM markdown is genuine, harvested from irs.gov, with `source_url` and `retrieved` in each file's front matter — cite subsections as written there.
- `jcl/`, `ctl/`, `sched/` and `catlg/` do not execute, but they are internally consistent and can be right or wrong against the COBOL. That is why they are in scope.
- Twelve well-sourced findings beat sixty speculative ones.

## Forbidden Actions

- Do **not** open anything under `irm/` before Step 1 is written down. Reading the IRM first anchors extraction on what is expected rather than what is present and produces agreement that is not there — this is the primary failure mode of this playbook.
- Do **not** report a rule that falls inside a `≡` / `> REDACTED IN SOURCE` span as `DRIFT` or `IRM-ONLY`. It is `UNVERIFIABLE`. A false positive here is the worst possible outcome in front of this audience.
- Do **not** invent a citation. If a rule cannot be located in the code or the IRM, say so explicitly.
- Do **not** treat a comment as evidence of behavior.
- Do **not** look for or use an answer key; none exists in the repository.
- Do **not** modify the corpus, and do **not** commit anything — including the report. This playbook is read-only apart from the gitignored file it writes under `reports/`.
