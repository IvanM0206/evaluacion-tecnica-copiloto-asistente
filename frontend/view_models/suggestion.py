"""`POST /api/copilot/analyze`: la sugerencia del copiloto que revisa el operador."""

from __future__ import annotations

from pydantic import BaseModel, Field

from frontend.view_models.checklist import ChecklistItemVM
from frontend.view_models.field import FieldVM
from frontend.view_models.similar_case import SimilarCaseVM


class SuggestionVM(BaseModel):
    provider: str
    street: FieldVM
    street_number: FieldVM
    intersection: FieldVM
    neighborhood: FieldVM
    category: str
    subcategory: str
    priority: str
    priority_rationale: str
    checklist: list[ChecklistItemVM]
    pre_arrival_instructions: list[str]
    risks: list[str]
    suggested_resources: str
    summary: str
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    similar_cases: list[SimilarCaseVM] = Field(default_factory=list)

    @property
    def confidence_pct(self) -> int:
        return round(self.confidence * 100)

    @property
    def checklist_pending_first(self) -> list[ChecklistItemVM]:
        """Primero las pendientes: es lo próximo que tiene que preguntar el operador."""
        return sorted(self.checklist, key=lambda c: c.answered)

    @property
    def answered_count(self) -> int:
        return sum(1 for c in self.checklist if c.answered)

    @property
    def location_summary(self) -> str:
        street = " ".join(p for p in (self.street.display_value, self.street_number.display_value) if p)
        return street or "Sin calle detectada"

    @property
    def location_fields(self) -> list[tuple[str, str, FieldVM]]:
        return [
            ("street", "Calle", self.street),
            ("street_number", "Altura", self.street_number),
            ("intersection", "Intersección", self.intersection),
            ("neighborhood", "Barrio", self.neighborhood),
        ]
