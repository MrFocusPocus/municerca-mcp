"""Pydantic models for all tool inputs and outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["reclamo", "solicitud", "sugerencia", "consulta", "felicitacion"]
TicketState = Literal["abierto", "escalado"]


class Tramite(BaseModel):
    tramite_id: str
    nombre: str
    categoria: str
    descripcion: str
    requisitos: list[str]
    costo: str | None = Field(description="None means not published in the knowledge base")
    canal: str
    horario: str | None = Field(description="None means not published in the knowledge base")
    keywords: list[str] = Field(default_factory=list, exclude=True)
    fuente: str


class TramiteMatch(BaseModel):
    tramite_id: str
    nombre: str
    categoria: str
    score: float


class SearchResult(BaseModel):
    matches: list[TramiteMatch]


class TicketCreated(BaseModel):
    ticket_id: str
    status: TicketState
    sla_date: str


class TicketStatus(BaseModel):
    ticket_id: str
    category: Category
    status: TicketState
    created_at: str
    sla_date: str
    escalated: bool


class Escalation(BaseModel):
    ticket_id: str
    queue_id: int
    status: TicketState
    queued_at: str


class AuditEntry(BaseModel):
    id: int
    actor: str
    action: str
    entity: str
    timestamp: str
