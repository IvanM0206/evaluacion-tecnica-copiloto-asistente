"""Una pregunta del checklist dinámico: del catálogo de protocolo o sugerida por el LLM."""

from __future__ import annotations

from pydantic import BaseModel


class ChecklistItemVM(BaseModel):
    question: str
    answered: bool
    answer: str | None = None
    evidence: str | None = None
    grounded: bool = False
    source: str = "protocol"  # "protocol" | "ai"

    @property
    def suggested_by_ai(self) -> bool:
        return self.source == "ai"
