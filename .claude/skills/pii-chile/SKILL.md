---
name: pii-chile
description: Rules for handling personal data of Chilean residents in this repo under Ley 19.628. Load before touching storage, traces, logging, error messages, eval results or anything that persists or prints resident text.
---

# PII rules for municerca-mcp (Ley 19.628)

Ley 19.628 sobre protección de la vida privada treats any information about an identified or
identifiable natural person as personal data. In this repo that means, at minimum:

| Data | Examples | Marker after redaction |
|---|---|---|
| RUT | `12.345.678-5`, `7654321-k` | `[RUT]` |
| Phone | `+56 9 8765 4321`, `987654321`, `2 2345 6789` | `[TELEFONO]` |
| Email | `nombre@correo.ejemplo` | `[EMAIL]` |
| Street address of a person | "vivo en Las Camelias 123" | not automated, see limits |

## Rules

1. Redact before persisting. Anything that reaches SQLite goes through
   `municerca_mcp.redaction.redact` first. There is no code path that stores raw resident text.
2. Never in logs, traces or error messages. Do not log tool arguments. Error messages carry a
   stable code and never echo input. Traces are redacted as a whole line in
   `agent.run.serialize_trace`.
3. Never in eval results. `evals/run.py` scrubs every answer it writes.
4. Return counts, not values. `TicketCreated.redactions` reports how many items were redacted.
5. Test data is synthetic. Use the fictional RUTs already in `evals/dataset.jsonl`. Never paste
   a real RUT, phone or email, including your own, into code, tests, docs or commits.
6. Do not ask the resident for a RUT. No tool in this server needs it.
7. Do not weaken the checker. `evals/checks.py` keeps its own PII patterns, independent from
   `redaction.py`. Do not make one import the other.

## Known limits (say so, do not hide them)

- Redaction is regex based. Names and free text addresses are not detected.
- A new format that slips through is an incident: add it to `evals/dataset.jsonl` and to
  `tests/test_redaction.py` first, then fix the pattern (see `docs/RUNBOOK.md`).

## Verify

- `uv run pytest tests/test_redaction.py`
- `uv run python scripts/check_pii.py` scans `traces/` and `*.log` for RUT patterns. It also
  runs as a git pre-commit hook (`make hooks`).
