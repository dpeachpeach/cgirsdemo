# Playbooks

Three reusable procedures for working this corpus. Each takes one input, writes a
markdown report under `reports/`, and prints a condensed table to the transcript.

| Playbook | Input | Question it answers |
|:---|:---|:---|
| [`irm-code-reconciliation.md`](irm-code-reconciliation.md) | a program name | Where does the code disagree with the IRM — and where do the five notations describing this job disagree with each other? |
| [`field-lineage-trace.md`](field-lineage-trace.md) | a copybook field name | Which programs touch these bytes, and do they agree on what the bytes mean? |
| [`port-and-characterize.md`](port-and-characterize.md) | a program name | Can the program be ported to Python with a test suite that proves equivalence, bugs included? |

Conventions shared by all three:

- **Sourced claims.** `path:line` for code and notations, subsection number for IRM. Never invent a citation.
- **Redactions are not drift.** Rules inside a `≡` / `> REDACTED IN SOURCE` span are `UNVERIFIABLE`.
- **Comments are not evidence.** They are deliberately stale; read behavior from the code.
- **Tables over prose, findings first, progress announced.** These are run live; bounded to roughly six minutes per program.
