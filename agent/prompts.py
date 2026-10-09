"""System prompts for the resident facing agent, versioned so evals can compare them."""

from __future__ import annotations

V0 = "Eres un asistente de la Municipalidad de Ejemplo. Ayuda a los vecinos."

PROMPTS: dict[str, str] = {"v0": V0}
DEFAULT_PROMPT = "v0"
