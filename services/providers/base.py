"""Contrato de los providers. El orquestador solo depende de esta interfaz."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from services.models import Category, RawExtraction, ReferenceCase

MIN_SIMILARITY = 0.2  # por debajo de esto un caso de referencia es una suposición, no un match


@dataclass(frozen=True)
class ExtractionContext:
    similar_cases: list[tuple[ReferenceCase, float]]
    candidate_questions: list[str]
    known_streets: list[str] = field(default_factory=list)
    # El caso con mejor puntaje de cada categoría en todo el catálogo (sigue aplicando leave-one-out).
    # Anchor de respaldo cuando los top-k casos similares no incluyen ninguno de la categoría elegida.
    category_anchors: dict[Category, tuple[ReferenceCase, float]] = field(default_factory=dict)

    def anchor_for(self, category: Category) -> tuple[ReferenceCase, float] | None:
        """Caso más similar de `category`: primero entre los top-k, si no en todo el catálogo
        siempre que sea lo bastante parecido. Un caso apenas relacionado traería el protocolo
        equivocado (p. ej. el checklist de un cartel caído para una fuga de gas), peor que ninguno."""
        in_top = next(((c, s) for c, s in self.similar_cases if c.category == category), None)
        if in_top:
            return in_top
        fallback = self.category_anchors.get(category)
        return fallback if fallback and fallback[1] >= MIN_SIMILARITY else None


class ProviderError(RuntimeError):
    """Se lanza cuando un provider no puede devolver un RawExtraction válido."""


class ExtractionProvider(Protocol):
    name: str

    def extract(self, transcript: str, ctx: ExtractionContext) -> RawExtraction: ...
