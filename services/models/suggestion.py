"""Lo que devuelve la API tras el grounding + enriquecimiento con el catálogo, y el request que lo pide."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.choices import Category, Priority


class GroundedField(BaseModel):
    value: str | None
    evidence: str | None
    grounded: bool = Field(description="True si la evidencia aparece en la transcripción.")
    normalized: str | None = None


ChecklistSource = Literal["protocol", "ai"]


class ChecklistItem(BaseModel):
    question: str
    answered: bool
    answer: str | None = None
    evidence: str | None = None
    grounded: bool = False
    source: ChecklistSource = Field(
        "protocol", description="'protocol': del catálogo. 'ai': pregunta extra sugerida por el LLM."
    )


class SimilarCase(BaseModel):
    id: str
    subcategory: str
    priority: Priority
    score: float


class CopilotSuggestion(BaseModel):
    provider: str
    street: GroundedField
    street_number: GroundedField
    intersection: GroundedField
    neighborhood: GroundedField
    category: Category
    subcategory: str
    priority: Priority
    priority_rationale: str
    checklist: list[ChecklistItem]
    pre_arrival_instructions: list[str]
    risks: list[str]
    suggested_resources: str
    summary: str
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    similar_cases: list[SimilarCase] = Field(default_factory=list)
    simulated: bool = Field(
        False, description="True si se pidió simular el LLM: lo marcado como IA son respuestas de ejemplo fijas."
    )


class AnalyzeRequest(BaseModel):
    transcript: str = Field(min_length=10, max_length=20_000)
    simulate_llm: bool = Field(
        False, description="Mock + respuestas de ejemplo para las funciones que solo existen con un LLM real."
    )
