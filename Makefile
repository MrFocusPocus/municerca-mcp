.PHONY: check lint type test pii hooks evals report

check: lint type test pii

lint:
	uv run ruff check .
	uv run ruff format --check .

type:
	uv run mypy

test:
	uv run pytest -q

pii:
	uv run python scripts/check_pii.py

hooks:
	git config core.hooksPath .githooks

evals:
	uv run python -m evals.run --label local --out evals/results/local.json

report:
	uv run python scripts/report.py
