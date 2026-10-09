# Demo walkthrough (10 minutes)

All numbers below come from `evals/results/v0.json` and `evals/results/v1.json`, two real runs
on 2026-10-09. Both ran on `deepseek-flash` (agent) and `deepseek-v4-pro` (judge) through
DeepSeek's Anthropic compatible endpoint. The code defaults to Claude models and switches by
environment variables only.

## Script

| Min | Show | Say |
|---|---|---|
| 0 to 1 | `git log --oneline` | The log is the loop: intent, spec, plan, scaffold, server, harness, evals, v0 result, fix, v1 result, report, controls. |
| 1 to 2 | `docs/intent.md`, `docs/spec.md` | Problem, constraints (Ley 19.628, grounding), failure modes and non-goals were written before code. |
| 2 to 3 | `CLAUDE.md` | Commands, conventions, "things Claude gets wrong", and the rule that `make check` passes before anything is reported done. |
| 3 to 4 | `src/municerca_mcp/server.py`, `make check` | Five typed tools and one resource. 37 deterministic tests, mypy strict, no LLM. |
| 4 to 5 | `uv run python -m agent.run "¿En qué horario atienden para el certificado de residencia?"` | Live: the KB has no horario, the agent says so and offers a ticket. Latency, tokens and cost print at the end. |
| 5 to 7 | `evals/dataset.jsonl`, `evals/checks.py`, `report.html` | 24 Spanish cases. v0 passed 5 of 24, v1 passed 23 of 24. Show the flipped cases. |
| 7 to 8 | `git show eval-v0:src/municerca_mcp/server.py`, `src/municerca_mcp/redaction.py` | v0 is a real commit, not a flag. The fix came with unit tests that pin it. |
| 8 to 9 | `.claude/settings.json`, `echo '{"m":"12.345.678-5"}' > traces/x.jsonl && make pii; rm traces/x.jsonl` | An agent cannot weaken the checks, and a RUT in a trace blocks the commit. |
| 9 to 10 | `.github/workflows/evals.yml`, `REVIEW.md`, `docs/RUNBOOK.md` | Evals gate PRs, review has three passes, every incident becomes an eval case. |

## What the eval caught

- v0: 5 of 24 (21%), USD 0.0406. v1: 23 of 24 (96%), USD 0.0309. Threshold 90%.
- 5 `pii` cases failed in v0 because RUT, phone or email reached the stored ticket or the trace.
- 4 cases (T02, T04, E01, E03) failed because the naive agent asked for more data instead of
  creating the ticket or escalating.
- 9 cases failed only on `cites_tramite_id`, a format the naive prompt was never told about.
  That part of the jump measures instruction following, not safety. Say this out loud.
- The naive model did not invent a horario in v0. Its grounding failures were format only.
- 1 case still fails in v1 (O01). It is listed in the report and in the runbook.

## Artifact to must-have

| Arcadia must-have | Where it is in this repo |
|---|---|
| Software factory: the fast path is the safe path | `Makefile`, `pyproject.toml`, `CLAUDE.md`, `.claude/settings.json` hooks, `.githooks/pre-commit` |
| AI-native SDLC loop | `docs/intent.md`, `docs/spec.md`, `docs/plan.md`, one commit per step, `REVIEW.md` |
| Before and after numbers | `evals/results/v0.json`, `evals/results/v1.json`, `report.html` |
| Good evals | `evals/dataset.jsonl`, `evals/checks.py` (deterministic first), `evals/judge.py` with `evals/rubric.md` |
| Coding agents wired into pipelines | `CLAUDE.md` verification block, hooks, `.github/workflows/evals.yml` on changes to `CLAUDE.md` and `.claude/**` |
| MCP servers | `src/municerca_mcp/server.py`, `tests/test_stdio.py` |
| Human in the loop with audit trail | `escalate_to_human`, `review_queue`, append-only `audit_log` enforced by SQLite triggers |
| Production Python | pydantic models, `mypy --strict`, 37 tests, `uv` packaging, typed errors that never echo input |
| Instrumentation | `agent/run.py` traces, `agent/pricing.py`, `scripts/report.py` |

## Likely questions

1. **How do you know the eval is not just grading your own homework?**
   The evals were committed before the fix (`git log`), v0 is the tagged commit `eval-v0`, and
   `evals/checks.py` keeps its own PII patterns instead of importing `redaction.py`.

2. **Why deterministic checks first and a judge second?**
   String and database checks are free, repeatable and cannot be argued with. The judge only
   runs on `missing_info` and `out_of_scope` cases, and only after deterministic checks pass,
   so it cannot rescue a failure. Its rubric is in `evals/rubric.md`.

3. **What stops a coding agent from making the eval pass by editing the eval?**
   A PreToolUse hook blocks edits to `tests/` and `evals/dataset.jsonl` unless
   `ALLOW_TEST_EDITS=1`. It guards the Edit and Write tools, not shell writes, so `REVIEW.md`
   pass 3 and CI are the backstop. That limit is written in `docs/RUNBOOK.md`.

4. **How is PII handled?**
   `create_oirs_ticket` and `escalate_to_human` redact RUT, phone and email before SQLite.
   Traces are redacted as a whole serialized line. A pre-commit check blocks any RUT in
   `traces/` or logs. Limits: regex only, names and free text addresses are not covered.

5. **What does it cost and how fast is it?**
   About USD 0.0007 per conversation for the agent in v1, p50 3.9 s and p95 5.4 s, with cases
   running concurrently and including server startup. A full run of 24 cases plus judge cost
   USD 0.03. Cost is an estimate from list prices in `agent/pricing.py`.

6. **Where is the human in the loop?**
   `escalate_to_human` puts the ticket in `review_queue` and writes an audit entry (actor,
   action, entity, UTC timestamp). SQLite triggers abort any UPDATE or DELETE on `audit_log`,
   and `tests/test_tools.py` proves it.

7. **What is still wrong with it?**
   One case fails in v1. Each result is a single run, so there is no variance estimate. The
   runs used DeepSeek, not Claude. The `ci` workflow is green on GitHub, but the `evals` workflow has not run
   yet because the repository has no API key secret. There is no contact vault, so a ticket cannot be called back.

8. **How would this roll out to a team?**
   The reusable parts are not the municipal logic: `CLAUDE.md` with a verification block, the
   hooks, the eval runner with a threshold exit code, the two workflows and `REVIEW.md`. Those
   become the template. `docs/RUNBOOK.md` adds the rule that every incident becomes an eval case.
