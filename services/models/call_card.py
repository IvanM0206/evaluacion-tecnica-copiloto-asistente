"""Carta de Llamada derivada por el operador (mismos nombres de campo que backend.CallCard)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from backend.choices import Category, Priority


class CallCardCreate(BaseModel):
    """La Carta de Llamada validada que el operador deriva al despacho."""

    transcript: str
    street: str = Field(min_length=1)
    street_number: str | None = None
    intersection: str | None = None
    neighborhood: str | None = None
    category: Category
    subcategory: str
    priority: Priority
    answered_questions: list[str] = Field(default_factory=list)
    pending_questions: list[str] = Field(default_factory=list)
    instructions_given: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    suggested_resources: str | None = None
    operator_notes: str | None = None
    ai_confidence: float | None = None
    ai_provider: str | None = None


class CallCard(CallCardCreate):
    id: int
    created_at: datetime
