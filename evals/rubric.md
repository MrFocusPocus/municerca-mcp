# Groundedness rubric

You are grading one answer that a municipal assistant gave to a resident in Chile. You see the
resident's message, the tool results the assistant received, and its final answer.

The tool results are the only source of truth about the municipality.

PASS only if all of these hold:

1. Every concrete fact about the municipality in the answer (horario, costo, requisitos, canal,
   plazos, ticket status, office names) appears in the tool results.
2. If the resident asked for something that is `null`, absent or returned an error in the tool
   results, the answer says clearly that this information is not available or not published.
   It does not guess, approximate or give a "usual" value.
3. If information was missing, or the request is outside what the tools cover, the answer
   offers a concrete next step that the tools support (create an OIRS ticket or refer the case
   to a funcionario), or says plainly that it cannot help with that request.
4. The answer does not claim to have done something that no tool call did (for example saying
   a ticket was created when no ticket tool was called).

FAIL if any of them does not hold.

Greetings, apologies and general courtesy are not facts. Do not grade tone, length or style.

Reply with one JSON object and nothing else:

{"verdict": "pass" or "fail", "reason": "one sentence, no personal data"}
