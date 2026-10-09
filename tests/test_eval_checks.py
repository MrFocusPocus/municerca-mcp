"""The eval checks are code too: pin them so a broken checker cannot pass silently."""

from __future__ import annotations

import json
from pathlib import Path

from evals.checks import Observation, find_pii, run_checks, scrub

DATASET = Path(__file__).resolve().parent.parent / "evals" / "dataset.jsonl"


def _obs(**overrides: object) -> Observation:
    base: dict[str, object] = {
        "tools_called": ["search_tramites", "get_tramite"],
        "final_answer": "Trámite permiso-circulacion: requisitos...",
        "trace_line": "{}",
        "stored_text": [],
        "tickets": 0,
        "escalations": 0,
        "error": None,
    }
    return Observation(**{**base, **overrides})  # type: ignore[arg-type]


def test_find_pii_formats() -> None:
    assert find_pii("rut 12.345.678-5") == ["rut"]
    assert find_pii("rut 7654321-k") == ["rut"]
    assert find_pii("cel +56 9 8765 4321") == ["phone"]
    assert find_pii("fono 987654321") == ["phone"]
    assert find_pii("a juan.perez@correo.ejemplo") == ["email"]


def test_find_pii_ignores_ticket_ids_dates_and_prices() -> None:
    clean = "OIRS-2026-000001 creado 2026-10-09T16:20:11+00:00, SLA 2026-10-23, costo $32.000"
    assert find_pii(clean) == []
    assert find_pii("[RUT] [PHONE] [EMAIL]") == []


def test_scrub_removes_all_patterns() -> None:
    assert find_pii(scrub("12.345.678-5, 987654321, a@b.cl")) == []


def test_checks_pass_and_fail() -> None:
    expect = {"tools_called": ["get_tramite"], "cite": "permiso-circulacion"}
    assert all(run_checks(expect, _obs()).values())
    failed = run_checks(expect, _obs(final_answer="No sé", stored_text=["rut 12.345.678-5"]))
    assert failed["cites_tramite_id"] is False
    assert failed["no_pii_in_stored_ticket"] is False


def test_forbidden_pattern_catches_invented_horario() -> None:
    expect = {"answer_forbidden": [r"\b\d{1,2}:\d{2}\b"]}
    assert (
        run_checks(expect, _obs(final_answer="Atienden de 9:00 a 14:00"))["answer_forbidden:0"]
        is False
    )


def test_dataset_is_well_formed() -> None:
    cases = [json.loads(line) for line in DATASET.read_text("utf-8").splitlines() if line.strip()]
    assert 20 <= len(cases) <= 25
    assert len({c["id"] for c in cases}) == len(cases)
    assert {c["category"] for c in cases} == {
        "lookup",
        "ticket",
        "pii",
        "missing_info",
        "out_of_scope",
        "escalation",
    }
