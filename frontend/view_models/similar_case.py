"""Un caso de referencia que el copiloto encontró parecido a la llamada."""

from __future__ import annotations

from pydantic import BaseModel


class SimilarCaseVM(BaseModel):
    id: str
    subcategory: str
    priority: str
    score: float
