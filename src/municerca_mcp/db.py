"""SQLite storage: tickets, human review queue and an append-only audit log."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from municerca_mcp.models import AuditEntry, Category, Escalation, TicketCreated, TicketStatus

# Demo policy, not a legal statement (see docs/intent.md).
SLA_BUSINESS_DAYS: dict[str, int] = {
    "reclamo": 10,
    "solicitud": 15,
    "sugerencia": 20,
    "consulta": 5,
    "felicitacion": 20,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT UNIQUE,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    contact TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    sla_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL UNIQUE,
    reason TEXT NOT NULL,
    queued_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
"""


class TicketNotFoundError(LookupError):
    """Raised for an unknown ticket id. The message never echoes the id."""


def add_business_days(start: date, days: int) -> date:
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


class Store:
    def __init__(self, path: str | Path) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def _audit(self, actor: str, action: str, entity: str) -> None:
        self._conn.execute(
            "INSERT INTO audit_log (actor, action, entity, timestamp) VALUES (?, ?, ?, ?)",
            (actor, action, entity, _now().isoformat()),
        )

    def create_ticket(
        self, category: Category, description: str, contact: str, now: datetime | None = None
    ) -> TicketCreated:
        created = now or _now()
        sla = add_business_days(created.date(), SLA_BUSINESS_DAYS[category])
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO tickets (category, description, contact, status, created_at, sla_date)"
                " VALUES (?, ?, ?, 'abierto', ?, ?)",
                (category, description, contact, created.isoformat(), sla.isoformat()),
            )
            ticket_id = f"OIRS-{created.year}-{cur.lastrowid:06d}"
            self._conn.execute(
                "UPDATE tickets SET ticket_id = ? WHERE id = ?", (ticket_id, cur.lastrowid)
            )
            self._audit("agent", "ticket.created", ticket_id)
        return TicketCreated(ticket_id=ticket_id, status="abierto", sla_date=sla.isoformat())

    def _ticket_row(self, ticket_id: str) -> sqlite3.Row:
        row: sqlite3.Row | None = self._conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if row is None:
            raise TicketNotFoundError("TICKET_NOT_FOUND: no ticket with that id")
        return row

    def get_status(self, ticket_id: str) -> TicketStatus:
        row = self._ticket_row(ticket_id)
        return TicketStatus(
            ticket_id=row["ticket_id"],
            category=row["category"],
            status=row["status"],
            created_at=row["created_at"],
            sla_date=row["sla_date"],
            escalated=row["status"] == "escalado",
        )

    def escalate(self, ticket_id: str, reason: str) -> Escalation:
        self._ticket_row(ticket_id)
        with self._conn:
            existing = self._conn.execute(
                "SELECT id, queued_at FROM review_queue WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if existing is not None:
                self._audit("agent", "ticket.escalation_repeated", ticket_id)
                return Escalation(
                    ticket_id=ticket_id,
                    queue_id=existing["id"],
                    status="escalado",
                    queued_at=existing["queued_at"],
                )
            queued_at = _now().isoformat()
            cur = self._conn.execute(
                "INSERT INTO review_queue (ticket_id, reason, queued_at) VALUES (?, ?, ?)",
                (ticket_id, reason, queued_at),
            )
            self._conn.execute(
                "UPDATE tickets SET status = 'escalado' WHERE ticket_id = ?", (ticket_id,)
            )
            self._audit("agent", "ticket.escalated", ticket_id)
        assert cur.lastrowid is not None
        return Escalation(
            ticket_id=ticket_id, queue_id=cur.lastrowid, status="escalado", queued_at=queued_at
        )

    def audit_entries(self) -> list[AuditEntry]:
        rows = self._conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
        return [AuditEntry(**dict(r)) for r in rows]

    def stored_text(self) -> list[str]:
        """Every free text value persisted, for PII checks in tests and evals."""
        out: list[str] = []
        for r in self._conn.execute("SELECT description, contact FROM tickets"):
            out.extend([r["description"], r["contact"]])
        out.extend(r["reason"] for r in self._conn.execute("SELECT reason FROM review_queue"))
        return out
