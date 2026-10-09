"""Deterministic unit tests for every tool. No LLM, no network."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from municerca_mcp import server
from municerca_mcp.db import Store, TicketNotFoundError, add_business_days
from municerca_mcp.models import TicketCreated


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db = tmp_path / "test.db"
    monkeypatch.setenv("MUNICERCA_DB", str(db))
    server.store.cache_clear()
    yield db
    server.store().close()
    server.store.cache_clear()


def _ticket() -> str:
    created: TicketCreated = server.create_oirs_ticket(
        "reclamo", "Luminaria apagada hace una semana en Pasaje Los Aromos", "vecina"
    )
    return created.ticket_id


# search_tramites


def test_search_ranks_expected_tramite_first() -> None:
    matches = server.search_tramites("renovar permiso de circulacion del auto").matches
    assert matches[0].tramite_id == "permiso-circulacion"
    assert matches == sorted(matches, key=lambda m: -m.score)


def test_search_is_accent_and_case_insensitive() -> None:
    assert server.search_tramites("ÁRBOL con ramas").matches[0].tramite_id == "poda-arboles"


def test_search_no_match_returns_empty() -> None:
    assert server.search_tramites("pasaporte visa consulado").matches == []


def test_search_caps_results() -> None:
    assert len(server.search_tramites("permiso patente registro comuna").matches) <= 5


# get_tramite


def test_get_tramite_returns_requirements() -> None:
    tramite = server.get_tramite("permiso-circulacion")
    assert tramite.horario == "Lunes a viernes de 08:30 a 14:00"
    assert "Seguro obligatorio (SOAP) vigente" in tramite.requisitos


def test_get_tramite_missing_horario_is_none_not_default() -> None:
    assert server.get_tramite("certificado-residencia").horario is None
    assert server.get_tramite("esterilizacion-mascotas").costo is None


def test_get_tramite_unknown_id() -> None:
    with pytest.raises(ValueError, match="TRAMITE_NOT_FOUND"):
        server.get_tramite("no-existe")


def test_kb_has_no_real_municipality_and_some_missing_horarios() -> None:
    tramites = json.loads(server.kb_resource())
    assert len(tramites) == 12
    assert all("Municipalidad de Ejemplo" in t["fuente"] for t in tramites)
    assert sum(1 for t in tramites if t["horario"] is None) >= 3


# create_oirs_ticket


def test_create_ticket_returns_id_and_sla() -> None:
    created = server.create_oirs_ticket(
        "reclamo", "Bache profundo en calle Los Olmos con Av. Ejemplo", "vecino"
    )
    assert created.ticket_id.startswith("OIRS-")
    assert created.status == "abierto"
    assert date.fromisoformat(created.sla_date) > datetime.now(UTC).date()


def test_sla_counts_business_days_only() -> None:
    # Friday 2026-10-09 plus 10 business days is Friday 2026-10-23.
    assert add_business_days(date(2026, 10, 9), 10) == date(2026, 10, 23)
    assert add_business_days(date(2026, 10, 9), 1) == date(2026, 10, 12)


def test_create_ticket_writes_audit_entry() -> None:
    ticket_id = _ticket()
    entries = server.store().audit_entries()
    assert [(e.actor, e.action, e.entity) for e in entries] == [
        ("agent", "ticket.created", ticket_id)
    ]
    assert entries[0].timestamp.endswith("+00:00")


# get_ticket_status


def test_ticket_status_roundtrip_hides_description() -> None:
    status = server.get_ticket_status(_ticket())
    assert status.status == "abierto"
    assert status.escalated is False
    assert "description" not in status.model_dump()
    assert "contact" not in status.model_dump()


def test_ticket_status_unknown_id_does_not_echo_input() -> None:
    with pytest.raises(TicketNotFoundError) as exc:
        server.get_ticket_status("OIRS-2026-999999")
    assert "999999" not in str(exc.value)


# escalate_to_human


def test_escalate_queues_and_audits() -> None:
    ticket_id = _ticket()
    escalation = server.escalate_to_human(ticket_id, "Vecina molesta, pide hablar con una persona")
    assert escalation.status == "escalado"
    assert server.get_ticket_status(ticket_id).escalated is True
    actions = [e.action for e in server.store().audit_entries()]
    assert actions == ["ticket.created", "ticket.escalated"]


def test_escalate_is_idempotent_but_audited() -> None:
    ticket_id = _ticket()
    first = server.escalate_to_human(ticket_id, "primera vez")
    second = server.escalate_to_human(ticket_id, "segunda vez")
    assert first.queue_id == second.queue_id
    assert server.store().audit_entries()[-1].action == "ticket.escalation_repeated"


def test_escalate_unknown_ticket() -> None:
    with pytest.raises(TicketNotFoundError):
        server.escalate_to_human("OIRS-2026-999999", "motivo")


def test_audit_log_is_append_only(isolated_db: Path) -> None:
    _ticket()
    conn = sqlite3.connect(isolated_db)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE audit_log SET actor = 'x'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM audit_log")
    conn.close()


def test_store_reopens_existing_db(isolated_db: Path) -> None:
    ticket_id = _ticket()
    other = Store(isolated_db)
    assert other.get_status(ticket_id).ticket_id == ticket_id
    other.close()


# MCP surface


def test_mcp_exposes_five_tools_and_validates_input() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == {
        "search_tramites",
        "get_tramite",
        "create_oirs_ticket",
        "get_ticket_status",
        "escalate_to_human",
    }
    with pytest.raises(Exception, match="category"):
        asyncio.run(
            server.mcp.call_tool(
                "create_oirs_ticket",
                {"category": "otra", "description": "x" * 20, "contact": "c"},
            )
        )
