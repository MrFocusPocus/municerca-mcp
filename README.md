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
export ANTHROPIC_API_KEY=...                 # environment only
uv run python -m agent.run "¿Qué necesito para el permiso de circulación?"
make evals                                   # prints pass rate per category and cost
make report                                  # builds report.html
```

Models default to `claude-haiku-5-5` (agent) and `claude-sonnet-5-5` (judge). Override with
`MUNICERCA_AGENT_MODEL`, `MUNICERCA_JUDGE_MODEL` and `ANTHROPIC_BASE_URL`.

## Docs

- [docs/intent.md](docs/intent.md): problem, outcome, users, constraints
- [docs/spec.md](docs/spec.md): tools, schemas, failure modes, non-goals
- [docs/plan.md](docs/plan.md): files, order, risks, proof
- [CLAUDE.md](CLAUDE.md): commands, conventions and the verification rule for coding agents
