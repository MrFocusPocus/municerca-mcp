"""Redaction is pinned by unit tests: the eval found the gap, these keep it closed."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent.run import ToolCall, Trace, serialize_trace
from municerca_mcp import server
from municerca_mcp.models import TicketCreated
from municerca_mcp.redaction import redact


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db = tmp_path / "test.db"
    monkeypatch.setenv("MUNICERCA_DB", str(db))
    server.store.cache_clear()
    yield db
    server.store().close()
    server.store.cache_clear()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("mi rut es 12.345.678-5", "mi rut es [RUT]"),
        ("rut 7654321-k", "rut [RUT]"),
        ("RUT 15432198-K.", "RUT [RUT]."),
        ("llamar al +56 9 8765 4321", "llamar al [TELEFONO]"),
        ("fono 987654321", "fono [TELEFONO]"),
        ("fijo 2 2345 6789", "fijo [TELEFONO]"),
        ("mail juan.perez@correo.ejemplo", "mail [EMAIL]"),
    ],
)
def test_redact_formats(raw: str, expected: str) -> None:
    assert redact(raw)[0] == expected


def test_redact_counts_and_leaves_domain_text_alone() -> None:
    text = "Ticket OIRS-2026-000001, SLA 2026-10-23, costo $32.000, horario 08:30 a 14:00"
    assert redact(text)[0] == text
    _, counts = redact("12.345.678-5, 7654321-k, 987654321, a@b.cl")
    assert (counts.rut, counts.phone, counts.email) == (2, 1, 1)


def test_ticket_is_redacted_before_persisting(isolated_db: Path) -> None:
    created: TicketCreated = server.create_oirs_ticket(
        "reclamo",
        "Soy rut 12.345.678-5 y no pasa el camión de la basura por Pasaje Los Aromos",
        "+56 9 8765 4321 o vecina@correo.ejemplo",
    )
    assert (created.redactions.rut, created.redactions.phone, created.redactions.email) == (1, 1, 1)
    conn = sqlite3.connect(isolated_db)
    description, contact = conn.execute("SELECT description, contact FROM tickets").fetchone()
    conn.close()
    assert "12.345.678-5" not in description and "[RUT]" in description
    assert contact == "[TELEFONO] o [EMAIL]"
    assert "camión de la basura" in description


def test_escalation_reason_is_redacted() -> None:
    created: TicketCreated = server.create_oirs_ticket("reclamo", "Bache en calle Los Olmos", "x")
    server.escalate_to_human(created.ticket_id, "Pide que lo llamen al 987654321")
    assert server.store().stored_text()[-1] == "Pide que lo llamen al [TELEFONO]"


def test_trace_line_has_no_pii() -> None:
    trace = Trace(
        case_id="t",
        model="m",
        prompt_version="v1",
        message="mi rut es 12.345.678-5",
        tool_calls=[ToolCall("create_oirs_ticket", {"contact": "a@b.cl"}, False, "ok")],
        final_answer="Te llamaremos al 987654321",
    )
    line = serialize_trace(trace)
    assert "12.345.678-5" not in line and "a@b.cl" not in line and "987654321" not in line
    assert "[RUT]" in line and "[EMAIL]" in line and "[TELEFONO]" in line
