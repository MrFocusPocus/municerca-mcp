"""MuniCerca MCP server: knowledge base lookup, OIRS tickets and human escalation."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from municerca_mcp.db import Store
from municerca_mcp.kb import KnowledgeBase
from municerca_mcp.models import (
    Category,
    Escalation,
    SearchResult,
    TicketCreated,
    TicketStatus,
    Tramite,
)

mcp = FastMCP("municerca")


@lru_cache(maxsize=1)
def kb() -> KnowledgeBase:
    return KnowledgeBase.load()


@lru_cache(maxsize=1)
def store() -> Store:
    return Store(os.environ.get("MUNICERCA_DB", "municerca.db"))


@mcp.tool()
def search_tramites(
    query: Annotated[str, Field(min_length=2, max_length=200)],
) -> SearchResult:
    """Busca trámites municipales por texto. Devuelve hasta 5 coincidencias ordenadas."""
    return SearchResult(matches=kb().search(query))


@mcp.tool()
def get_tramite(tramite_id: str) -> Tramite:
    """Detalle de un trámite: requisitos, costo, canal y horario.

    Un campo null significa que el dato no está publicado en la base de conocimiento.
    """
    tramite = kb().get(tramite_id)
    if tramite is None:
        raise ValueError("TRAMITE_NOT_FOUND: no trámite with that id")
    return tramite


@mcp.tool()
def create_oirs_ticket(
    category: Category,
    description: Annotated[str, Field(min_length=10, max_length=2000)],
    contact: Annotated[str, Field(max_length=200)],
) -> TicketCreated:
    """Crea una solicitud OIRS. Devuelve el número de ticket y la fecha de respuesta (SLA)."""
    return store().create_ticket(category, description, contact)


@mcp.tool()
def get_ticket_status(ticket_id: str) -> TicketStatus:
    """Estado de una solicitud OIRS existente."""
    return store().get_status(ticket_id)


@mcp.tool()
def escalate_to_human(
    ticket_id: str,
    reason: Annotated[str, Field(min_length=3, max_length=500)],
) -> Escalation:
    """Deriva un ticket existente a un funcionario. Queda en la cola de revisión y en auditoría."""
    return store().escalate(ticket_id, reason)


@mcp.resource("municerca://kb/tramites")
def kb_resource() -> str:
    """Base de conocimiento completa de trámites de la Municipalidad de Ejemplo."""
    return json.dumps([t.model_dump() for t in kb().all()], ensure_ascii=False)


@mcp.resource("municerca://kb/tramites/{tramite_id}")
def kb_tramite_resource(tramite_id: str) -> str:
    tramite: Tramite = get_tramite(tramite_id)
    return tramite.model_dump_json()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
