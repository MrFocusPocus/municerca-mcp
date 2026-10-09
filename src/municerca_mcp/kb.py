"""Knowledge base loading and deterministic search."""

from __future__ import annotations

import json
import re
import unicodedata
from importlib import resources

from municerca_mcp.models import Tramite, TramiteMatch

MAX_MATCHES = 5
_STOPWORDS = frozenset(
    "a al como con cual cuando de del donde el en es la las lo los me mi para por que "
    "quiero necesito se si su un una y o hacer hago puedo tengo saber sobre".split()
)


def normalize(text: str) -> str:
    """Lowercase and strip accents so 'circulación' matches 'circulacion'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", normalize(text)) if t not in _STOPWORDS}


class KnowledgeBase:
    def __init__(self, tramites: list[Tramite]) -> None:
        self._by_id = {t.tramite_id: t for t in tramites}

    @classmethod
    def load(cls) -> KnowledgeBase:
        raw = resources.files("municerca_mcp").joinpath("data/tramites.json").read_text("utf-8")
        return cls([Tramite.model_validate(item) for item in json.loads(raw)])

    def all(self) -> list[Tramite]:
        return list(self._by_id.values())

    def get(self, tramite_id: str) -> Tramite | None:
        return self._by_id.get(tramite_id)

    def search(self, query: str) -> list[TramiteMatch]:
        """Rank by weighted token overlap: nombre 3, keywords 2, descripcion 1."""
        terms = tokenize(query)
        scored: list[TramiteMatch] = []
        for t in self._by_id.values():
            score = (
                3 * len(terms & tokenize(t.nombre))
                + 2 * len(terms & tokenize(" ".join(t.keywords)))
                + len(terms & tokenize(t.descripcion))
            )
            if score > 0:
                scored.append(
                    TramiteMatch(
                        tramite_id=t.tramite_id,
                        nombre=t.nombre,
                        categoria=t.categoria,
                        score=float(score),
                    )
                )
        scored.sort(key=lambda m: (-m.score, m.tramite_id))
        return scored[:MAX_MATCHES]
