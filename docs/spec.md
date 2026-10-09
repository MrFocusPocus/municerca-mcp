# Spec: municerca-mcp

Derived from [intent.md](intent.md). Transport: MCP over stdio by default, streamable HTTP for
hosted use (see Transports). All tool inputs and outputs
are pydantic models. Errors are returned as MCP tool errors with a stable `code` and a message
that never echoes user supplied text.

## Tools

### search_tramites(query: str) -> SearchResult

- Input: `query`, 2 to 200 chars.
- Output: `matches: list[TramiteMatch]` (max 5), each `{tramite_id, nombre, categoria, score}`,
  ordered by score descending. Empty list when nothing matches.
- Ranking: deterministic token overlap over nombre, descripción and keywords, case and accent
  insensitive. No embeddings, no network.

### get_tramite(tramite_id: str) -> Tramite

- Output: `{tramite_id, nombre, categoria, descripcion, requisitos: list[str], costo: str | None,
  canal: str, horario: str | None, fuente: str}`.
- `horario` and `costo` may be `None`. `None` means "not published in the knowledge base".
  The server never fills a default.
- Error `TRAMITE_NOT_FOUND` for an unknown id.

### create_oirs_ticket(category, description, contact) -> TicketCreated

- `category`: one of `reclamo`, `solicitud`, `sugerencia`, `consulta`, `felicitacion`.
- `description`: 10 to 2000 chars. `contact`: free text (phone, email or name), max 200 chars.
- Behavior: redact RUT, phone and email from `description` and `contact`, then persist to
  SQLite. Unredacted input is never written to disk, logged or returned.
- Output: `{ticket_id, status: "abierto", sla_date, redactions: {rut, phone, email}}` where
  `redactions` holds counts only. `ticket_id` format: `OIRS-YYYY-NNNNNN`.
- `sla_date`: creation date plus N business days (Monday to Friday) per category. N is demo
  policy in config.
- Writes an audit entry (`actor=agent`, `action=ticket.created`).
- Invalid category or description length is rejected by schema validation before the tool
  body runs.

### get_ticket_status(ticket_id: str) -> TicketStatus

- Output: `{ticket_id, category, status, created_at, sla_date, escalated: bool}`.
- Does not return description or contact.
- Error `TICKET_NOT_FOUND`.

### escalate_to_human(ticket_id: str, reason: str) -> Escalation

- Behavior: redact `reason`, insert into `review_queue`, set ticket status `escalado`, append
  audit entry (`actor=agent`, `action=ticket.escalated`, `entity=ticket_id`, UTC timestamp).
- Idempotent: escalating an already escalated ticket returns the existing queue entry and
  still writes an audit entry (`ticket.escalation_repeated`).
- Output: `{ticket_id, queue_id, status: "escalado", queued_at}`.
- Error `TICKET_NOT_FOUND`.

## Resource

- `municerca://kb/tramites`: the full knowledge base as JSON.
- `municerca://kb/tramites/{tramite_id}`: one trámite.

## Transports

- stdio (default): `municerca-mcp`. Used by the harness, the evals and the tests.
- Streamable HTTP: `MUNICERCA_TRANSPORT=http`, endpoint `/mcp`, port from `PORT`. Stateless.
  Every request needs `Authorization: Bearer <MUNICERCA_AUTH_TOKEN>`. The server refuses to
  start over HTTP without a token of at least 32 characters. `/healthz` is the only public path.
- The token is one shared secret, read from the environment. There are no per client
  identities, so the audit `actor` is always `agent`.

## Storage

SQLite, path from `MUNICERCA_DB` (default `./municerca.db`). Tables: `tickets`, `review_queue`,
`audit_log`. `audit_log` is append-only, enforced by triggers that abort `UPDATE` and `DELETE`.
Columns: `id, actor, action, entity, timestamp`.

## Agent harness and traces

`agent/run.py` connects to the server over stdio, runs one resident message through Claude
with the MCP tools, and appends one JSON line to `traces/` with: `case_id`, `model`,
`prompt_version`, `tool_calls` (name, arguments, is_error), `latency_ms`, `input_tokens`,
`output_tokens`, `cost_usd`, `final_answer`. Traces pass through the same redaction as
tickets before they are written.

## Failure modes and expected behavior

| Failure | Expected behavior |
|---|---|
| Resident pastes RUT, phone or email | Stored ticket, trace and logs contain only redaction markers |
| Horario or costo missing in KB | Agent says it is not published, offers ticket or escalation, invents nothing |
| Unknown trámite or out of scope request | Agent says it cannot help with that, creates no ticket |
| Angry resident or explicit request for a person | Ticket is created, then escalated, audit entry exists |
| Unknown ticket id | `TICKET_NOT_FOUND`, agent does not guess a status |
| Invalid tool input | Typed error with code, no user text echoed |
| Model loops on tools | Harness stops at a max turn limit and records `stopped_reason` |
| Anthropic API error or timeout | Harness records the error in the trace, eval counts the case as failed |

## Evals

- `evals/dataset.jsonl`: 20 to 25 cases, categories: `lookup`, `ticket`, `pii`,
  `missing_info`, `out_of_scope`, `escalation`.
- Deterministic checks first: expected tool called, forbidden tool not called, ticket created,
  no PII pattern in stored ticket or trace, answer cites `tramite_id`.
- LLM judge (rubric in `evals/rubric.md`) only for groundedness, where string checks cannot
  decide. The judge sees the tool results and the answer and returns pass or fail plus a reason.
- Runner prints pass rate per category and overall, total cost, and exits non-zero below a
  threshold (default 0.9).

## Non-goals

- No real municipality data, no integration with real OIRS or CRM systems.
- No resident authentication (ClaveÚnica), no authorization model.
- No voice channel (the ElevenLabs and Twilio layer of the original product is not rebuilt).
- No semantic or vector search.
- No contact vault: contact is stored masked only, so a real callback is not possible.
- No per client identity or OAuth on the HTTP transport, no multi tenant support.
- No durable storage when hosted: the Cloud Run demo keeps SQLite on the instance's temporary
  disk, so tickets disappear when the instance is recycled.
- Redaction does not claim to catch names or every free text address.
