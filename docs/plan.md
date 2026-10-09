# Plan: municerca-mcp

Implements [spec.md](spec.md). Hard stop for building: 14:15 (America/Santiago), status at 13:45.
Each step below is one commit.

## Files

```
pyproject.toml, Makefile, README.md, CLAUDE.md
src/municerca_mcp/
  models.py        pydantic models for all tool I/O
  kb.py            load and search the knowledge base
  data/tramites.json   12 trámites, Municipalidad de Ejemplo, some without horario
  db.py            SQLite schema, tickets, review queue, append-only audit log
  sla.py           business day SLA per category
  redaction.py     RUT, phone, email redaction (added in the fix step, see below)
  server.py        FastMCP server: 5 tools + KB resource
agent/
  prompts.py       system prompts v0 (naive) and v1 (grounded)
  pricing.py       USD per million tokens per model
  run.py           stdio MCP client + Claude tool loop + JSONL trace
evals/
  dataset.jsonl    20 to 25 Spanish cases
  checks.py        deterministic checks
  judge.py, rubric.md   groundedness judge
  run.py           runner, per category pass rate, cost, threshold exit code
  results/v0.json, results/v1.json
scripts/report.py      static report.html
scripts/check_pii.py   pre-commit RUT check for traces/ and logs
tests/                 unit tests per tool, no LLM
.claude/settings.json, .claude/hooks/, .claude/skills/pii-chile/SKILL.md
.github/workflows/ci.yml, evals.yml
REVIEW.md, docs/RUNBOOK.md, DEMO.md
```

## Order

| # | Step | Priority | Target |
|---|---|---|---|
| 1 | intent, spec, plan (this commit) | Must | 12:30 |
| 2 | Scaffold (uv, ruff, mypy strict, pytest, Makefile) + CLAUDE.md | Must | 12:40 |
| 3 | Server v0 + unit tests for the 5 tools. No redaction yet. | Must | 13:00 |
| 4 | Agent harness with naive prompt v0, traces | Must | 13:10 |
| 5 | Eval dataset, checks, judge, runner | Must | 13:25 |
| 6 | Run evals on v0, commit `evals/results/v0.json`, tag `eval-v0` | Must | 13:30 |
| 7 | Fix: redaction in ticket, escalation and traces, prompt v1, new unit tests. Run, commit `v1.json` | Must | 13:45 |
| 8 | `scripts/report.py` and report.html | Must | 14:00 |
| 9 | pii-chile skill, hooks, pre-commit PII check | Should | 14:05 |
| 10 | CI workflows, REVIEW.md, README | Should | 14:10 |
| 11 | RUNBOOK.md, tag v0.1.0, DEMO.md | Nice | 14:15 |

Static files for steps 9 and 10 get written while eval runs are in flight.

## How v0 and v1 stay honest

- v0 is not a flag. It is the real code at the commit tagged `eval-v0`: minimal system prompt,
  `create_oirs_ticket` persists text as received. There is no switch in the final code that
  turns redaction off.
- Each result file records the git SHA, models, prompt version, timestamp and cost of the run
  that produced it.
- Evals are written and committed before the fix. The fix commit adds redaction and the unit
  tests that pin it.
- If v0 passes the threshold anyway, work stops and we design a harder case together.

## Design choices

- Each eval case spawns its own server process with its own temp SQLite file, so the runner can
  inspect what was actually stored, and cases run concurrently (4 at a time).
- Raw traces are runtime artifacts and are gitignored. v0 traces contain synthetic RUTs by
  construction, so they must not be committed. Result files carry the per case metrics the
  report needs, and the eval runner redacts anything it writes to results.
- The judge runs only on `missing_info` and `out_of_scope` cases, and only after deterministic
  checks pass, to keep cost and variance low.
- Models: agent `claude-haiku-5-5`, judge `claude-sonnet-5-5`, overridable with
  `MUNICERCA_AGENT_MODEL` and `MUNICERCA_JUDGE_MODEL`.

## Risks

| Risk | Mitigation |
|---|---|
| v0 passes because the model is careful by default | PII persistence and `tramite_id` citation are deterministic and do not depend on model caution. If overall still passes, stop and redesign. |
| LLM variance makes v1 flaky around 0.9 | Temperature 0 where supported, deterministic checks first, judge on few cases. Report the real number even if it is below threshold. |
| Time runs out | Cut from the bottom of the table. Steps 1 to 8 are protected. |
| Regex redaction misses a format | Unit tests cover dotted, undotted and `k` verifier RUTs, +56 and 9 digit phones. Limits are stated in spec non-goals. |
| Cost overrun | Haiku for the agent, max 6 turns and capped output tokens per case, cost printed per run. Budget: under USD 0.50 per full run, under USD 2 for the day. |
| MCP SDK or model API surprises | Smoke test one case end to end before writing the full dataset. |

## Proof

- `make check` (ruff, mypy --strict, pytest) passes at every commit from step 3 on.
- `uv run python -m evals.run` prints per category pass rate and cost. Expected: non-zero exit
  on v0, zero exit on v1. Whatever actually happens is what gets committed and reported.
- `report.html` shows v0 vs v1 by category, the cases that flipped, p50 and p95 latency, average
  tokens and USD per conversation, all read from the result files.
- `git log --oneline` reads as intent, spec, plan, scaffold, server, harness, evals, v0 result,
  fix, v1 result, report, controls.
