# municerca-mcp

MCP server for municipal citizen service (OIRS tickets, trámites) in a fictional Chilean
municipality, plus an agent harness and an eval suite. Read `docs/intent.md`, `docs/spec.md`
and `docs/plan.md` before changing behavior.

## Commands

- `uv sync` installs everything (Python 3.12).
- `make check` runs ruff check, ruff format --check, mypy --strict and pytest.
- `uv run municerca-mcp` starts the server over stdio.
- `uv run python -m agent.run "mensaje del vecino"` runs one conversation and writes a trace.
- `make evals` runs the eval suite (needs `ANTHROPIC_API_KEY` in the environment, costs money).
- `make report` rebuilds `report.html` from `evals/results/*.json`.

## Conventions

- Code, comments and docs in English. Domain data and resident conversations in Spanish.
- Every tool input and output is a pydantic model in `src/municerca_mcp/models.py`.
- Tool logic stays deterministic: no network, no LLM, no clock dependent branching in `src/`.
- Error messages carry a stable code (`TICKET_NOT_FOUND`) and never echo user input.
- A change in behavior changes `docs/spec.md` in the same commit.
- No em dashes in docs.

## Things Claude gets wrong

- Editing `evals/dataset.jsonl` or `tests/` to make a failing check pass. Fix the code. Those
  paths are blocked by a hook unless `ALLOW_TEST_EDITS=1`.
- Filling a missing `horario` or `costo` with a plausible default. `None` means "not published"
  and must stay `None` all the way to the resident.
- Logging or returning the resident's text in errors. RUT, phone, email and address never go to
  logs, traces or error messages. Load the `pii-chile` skill before touching storage or traces.
- Writing `ANTHROPIC_API_KEY` or any key to a file. Keys come from the environment only.
- Reporting numbers that no run produced. Every metric comes from a file in `evals/results/`.
- Using `mcp` 2.x APIs. This repo pins `mcp<2` and uses `mcp.server.fastmcp.FastMCP`.
- Using a real municipality name. The only municipality is "Municipalidad de Ejemplo".

## Verification

Before reporting anything as done:

```
make check
```

It must pass. If it fails, say so and show the output. If the change touches `src/`, `agent/`,
`CLAUDE.md` or `.claude/`, also run `make evals` and report the pass rate and cost it printed.
