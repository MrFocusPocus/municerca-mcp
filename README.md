# municerca-mcp

An MCP server that lets any agent serve residents of a fictional Chilean municipality
("Municipalidad de Ejemplo"): search trámites, create OIRS tickets with PII redaction, check
ticket status and escalate to a human with an append-only audit log. It ships with an agent
harness that writes cost and latency traces, and an eval suite that gates changes in CI.

## Run

```
uv sync
make check                                   # ruff, mypy --strict, pytest
uv run municerca-mcp                         # MCP server over stdio
MUNICERCA_TRANSPORT=http MUNICERCA_AUTH_TOKEN=... uv run municerca-mcp   # HTTP, bearer token
export ANTHROPIC_API_KEY=...                 # environment only
uv run python -m agent.run "¿Qué necesito para el permiso de circulación?"
make evals                                   # prints pass rate per category and cost
make report                                  # builds report.html from evals/results/
make hooks                                   # installs the PII pre-commit check
```

Models default to `claude-haiku-5-5` (agent) and `claude-sonnet-5-5` (judge). Override with
`MUNICERCA_AGENT_MODEL`, `MUNICERCA_JUDGE_MODEL` and `ANTHROPIC_BASE_URL`. Cost is estimated
from `agent/pricing.py`. For a model that is not in that table, set `MUNICERCA_PRICE_IN` and
`MUNICERCA_PRICE_OUT` (USD per million tokens) or the cost is reported as unknown.

## Docs

- [docs/intent.md](docs/intent.md): problem, outcome, users, constraints
- [docs/spec.md](docs/spec.md): tools, schemas, failure modes, non-goals
- [docs/plan.md](docs/plan.md): files, order, risks, proof
- [CLAUDE.md](CLAUDE.md): commands, conventions and the verification rule for coding agents
- [REVIEW.md](REVIEW.md): three review passes, Important vs Nit, nit cap
- [docs/RUNBOOK.md](docs/RUNBOOK.md): release, rollback, incidents become eval cases
- [DEMO.md](DEMO.md): 10 minute walkthrough
- `report.html`: v0 vs v1 eval results
