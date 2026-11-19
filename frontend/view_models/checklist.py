"""Una pregunta de protocolo del checklist dinámico."""

from __future__ import annotations

from pydantic import BaseModel


class ChecklistItemVM(BaseModel):
    question: str
    answered: bool
    answer: str | None = None
    evidence: str | None = None
    grounded: bool = False
