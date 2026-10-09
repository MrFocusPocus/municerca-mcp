.PHONY: check lint type test evals report

check: lint type test

lint:
	uv run ruff check .
	uv run ruff format --check .

type:
	uv run mypy

test:
	uv run pytest -q

evals:
	uv run python -m evals.run

report:
	uv run python scripts/report.py
