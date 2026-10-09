# Intent: municerca-mcp

## Problem

Residents ("vecinos") of a Chilean municipality ask the same questions and file the same
requests through OIRS (Oficina de Informaciones, Reclamos y Sugerencias) every day: what do I
need for a permiso de circulación, how do I report a broken streetlight, where is my ticket.
MuniCerca originally answered these with voice agents (ElevenLabs Agents + Twilio). That design
tied the municipal logic to one channel and one vendor, and it had no repeatable way to prove
that the agent stayed grounded or kept personal data out of storage.

## Outcome

One MCP server that exposes the municipal core (knowledge base lookup, OIRS tickets, human
escalation) so any agent, on any channel, can serve residents. Its behavior is proven by an
eval suite that runs in CI, not by a demo script.

Success for this repo, today:

1. Five tools and one resource work over stdio and pass deterministic unit tests.
2. An agent harness produces a JSONL trace per conversation with latency, tokens and USD cost.
3. An eval suite of 20 to 25 Spanish cases catches a real failure in a naive v0 and shows the
   fix in v1, with both result files committed and a static report comparing them.

## Users

- Resident: writes in Spanish, may be upset, may paste their RUT, phone or email unprompted.
- Municipal officer (funcionario): works the human review queue and needs an audit trail.
- Agent developer: connects any MCP client to the server and needs typed, predictable tools.
- Reviewer or auditor: needs to see who did what and when, and that PII was not stored.

## Constraints

- Ley 19.628 (protección de la vida privada): RUT, phone, email and street address are
  personal data. They are redacted before persisting and never appear in logs, traces or
  error messages. See `.claude/skills/pii-chile/SKILL.md`.
- Grounding: the agent may only state facts that a tool returned. If the knowledge base has no
  horario for a trámite, the agent says so and offers escalation. It never invents one.
- The municipality is fictional ("Municipalidad de Ejemplo"). No real municipality, person or
  RUT appears anywhere. All RUTs in the dataset are synthetic.
- `ANTHROPIC_API_KEY` comes from the environment only and is never written to a file.
- A full eval run costs well under USD 1 and prints its cost.
- No fabricated metrics. Every number in the report comes from a run that happened.
- Code and docs in English, domain data and resident conversations in Spanish.

## Decisions on the open questions (2026-10-09)

1. Contact data: the demo stores a masked contact only. A real callback needs an encrypted
   contact vault owned by the municipality, which is a non-goal here. Accepted limit: tickets
   in this repo cannot be called back.
2. Escalation without a ticket: not allowed. The shape is "create ticket, then escalate", so
   every escalation has an entity in the audit log.
3. SLA days per category are demo policy in config, not a legal statement.
4. Redaction is regex based and covers RUT, phone and email. Names and free text addresses are
   not claimed. Anything the regex misses is an incident and becomes a new eval case.
5. Resident authentication (ClaveÚnica) is out of scope. `get_ticket_status` therefore returns
   no description and no contact.

## Model provider for today's runs

The harness uses the anthropic SDK and reads `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` from
the environment. Defaults are `claude-haiku-5-5` (agent) and `claude-sonnet-5-5` (judge). The
runs for the show and tell use DeepSeek through its Anthropic compatible endpoint
(`https://api.deepseek.com/anthropic`), selected by environment only. Every result file records
the model and base URL host that actually produced it.
