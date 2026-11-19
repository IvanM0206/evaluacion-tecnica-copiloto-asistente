"""Contrato de los providers. El orquestador solo depende de esta interfaz."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from services.models import RawExtraction, ReferenceCase


@dataclass(frozen=True)
class ExtractionContext:
    similar_cases: list[tuple[ReferenceCase, float]]
    candidate_questions: list[str]
    known_streets: list[str] = field(default_factory=list)


class ProviderError(RuntimeError):
    """Se lanza cuando un provider no puede devolver un RawExtraction válido."""


class ExtractionProvider(Protocol):
    name: str

    def extract(self, transcript: str, ctx: ExtractionContext) -> RawExtraction: ...
