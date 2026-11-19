"""Carta de Llamada: la carta derivada (respuesta de la API) y el formulario de derivar (POST)."""

from __future__ import annotations

from datetime import datetime

from django.http import QueryDict
from pydantic import BaseModel, Field


class CallCardVM(BaseModel):
    """Una carta derivada tal como la devuelve GET/POST /api/cards (pantalla 'Cartas derivadas')."""

    id: int
    created_at: datetime
    transcript: str = ""
    street: str
    street_number: str | None = None
    intersection: str | None = None
    neighborhood: str | None = None
    category: str
    subcategory: str
    priority: str
    answered_questions: list[str] = Field(default_factory=list)
    pending_questions: list[str] = Field(default_factory=list)
    instructions_given: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    suggested_resources: str | None = None
    operator_notes: str | None = None
    ai_confidence: float | None = None
    ai_provider: str | None = None

    @property
    def location(self) -> str:
        base = " ".join(p for p in (self.street, self.street_number) if p)
        return f"{base} ({self.intersection})" if self.intersection else base

    @property
    def category_label(self) -> str:
        return self.category.replace("_", " ").capitalize()

    @property
    def confidence_pct(self) -> int | None:
        return None if self.ai_confidence is None else round(self.ai_confidence * 100)

    @property
    def question_count(self) -> int:
        return len(self.answered_questions) + len(self.pending_questions)


class CallCardFormVM(BaseModel):
    """El formulario 'Derivar Carta de Llamada', tal como lo envía el operador.

    Los inputs HTML usan los mismos nombres que la sugerencia (compartidos con
    `SuggestionVM.with_operator_edits`); `from_post` los mapea a estos campos.
    """

    transcript: str
    street: str = Field(min_length=1)
    street_number: str | None = None
    intersection: str | None = None
    neighborhood: str | None = None
    category: str
    subcategory: str
    priority: str
    answered_questions: list[str] = Field(default_factory=list)
    pending_questions: list[str] = Field(default_factory=list)
    instructions_given: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    suggested_resources: str | None = None
    operator_notes: str | None = None
    ai_confidence: float | None = None
    ai_provider: str | None = None

    @classmethod
    def from_post(cls, data: QueryDict) -> CallCardFormVM:
        def text(name: str) -> str | None:
            value = (data.get(name) or "").strip()
            return value or None

        questions = data.getlist("questions")
        answered = set(data.getlist("answered"))
        confidence = text("ai_confidence")
        return cls(
            transcript=data.get("transcript", ""),
            street=(data.get("street") or "").strip(),
            street_number=text("street_number"),
            intersection=text("intersection"),
            neighborhood=text("neighborhood"),
            category=data.get("category", ""),
            subcategory=(data.get("subcategory") or "").strip(),
            priority=data.get("priority", ""),
            answered_questions=[q for q in questions if q in answered],
            pending_questions=[q for q in questions if q not in answered],
            instructions_given=data.getlist("instructions"),
            risks=data.getlist("risks"),
            suggested_resources=text("suggested_resources"),
            operator_notes=text("operator_notes"),
            ai_confidence=float(confidence) if confidence else None,
            ai_provider=text("ai_provider"),
        )
