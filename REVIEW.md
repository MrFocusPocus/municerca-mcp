# Review guide

For human reviewers and for agentic review. Every PR gets three passes, in this order. Read
`docs/spec.md` and `docs/plan.md` first.

## Pass 1: bugs

- Does the code do what the PR says? Trace one happy path and one failure path by hand.
- Tool inputs validated by pydantic, outputs are models from `models.py`.
- SQLite writes happen inside one transaction. The audit entry is written in the same
  transaction as the change it records.
- New behavior has a deterministic unit test. `make check` passes.

## Pass 2: security and PII (Ley 19.628)

- No raw resident text reaches SQLite, logs, traces, error messages or eval results.
- New persistence or logging paths call `redaction.redact` and have a test in
  `tests/test_redaction.py`.
- No keys or secrets in code, config, fixtures or docs. Keys come from the environment only.
- `audit_log` stays append-only. No migration drops its triggers.
- `evals/checks.py` does not import from `municerca_mcp.redaction`.

## Pass 3: compliance with spec.md and plan.md

- Behavior matches `docs/spec.md`. If behavior changed, the spec changed in the same PR.
- Nothing from the spec's non-goals was added quietly.
- Changes to `src/`, `agent/`, `CLAUDE.md` or `.claude/` include the eval pass rate and cost in
  the PR description, taken from a real run.
- `tests/` and `evals/dataset.jsonl` were only edited to add or tighten checks. A PR that
  removes or loosens a check needs its own justification and a human approval.

## Severity

Important (blocks merge):

- Any PII path from pass 2.
- Wrong or invented data returned to a resident (a default for a missing horario, a guessed
  ticket status).
- A weakened or deleted test or eval case.
- Behavior that contradicts the spec without a spec change.
- A failing `make check`, or an eval pass rate below threshold.
- A broken audit trail.

Nit (does not block):

- Naming, wording, comment style, import order, small refactors, optional test additions.

## Nit cap

At most 5 nits per review. If there are more, post the 5 most useful and say how many were
left out. Important findings are never capped and always come first.

## Output format

```
## Important
1. <file>:<line> what is wrong, why it matters, suggested fix

## Nits (max 5)
1. <file>:<line> suggestion

## Verified
- what was checked and how (commands run, cases traced)
```
