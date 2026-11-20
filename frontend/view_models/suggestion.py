"""`POST /api/copilot/analyze`: la sugerencia del copiloto que revisa el operador."""

from __future__ import annotations

from django.http import QueryDict
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
    simulated: bool = False

    @property
    def confidence_pct(self) -> int:
        return round(self.confidence * 100)

    @property
    def checklist_pending_first(self) -> list[ChecklistItemVM]:
        """Primero las pendientes: es lo próximo que tiene que preguntar el operador."""
        return sorted(self.checklist, key=lambda c: c.answered)

    @property
    def has_ai_questions(self) -> bool:
        return any(c.suggested_by_ai for c in self.checklist)

    @property
    def answered_count(self) -> int:
        return sum(1 for c in self.checklist if c.answered)

    @property
    def location_summary(self) -> str:
        street = " ".join(p for p in (self.street.display_value, self.street_number.display_value) if p)
        return street or "Sin calle detectada"

    def with_operator_edits(self, form: QueryDict) -> SuggestionVM:
        """Vuelve a aplicar el formulario de derivar sobre la sugerencia, así una derivación
        fallida conserva las ediciones del operador (prioridad, tipo, ubicación y checklist)."""
        answered = set(form.getlist("answered"))
        return self.model_copy(
            update={
                "priority": form.get("priority") or self.priority,
                "category": form.get("category") or self.category,
                "subcategory": (form.get("subcategory") or "").strip(),
                "street": self.street.with_value(form.get("street")),
                "street_number": self.street_number.with_value(form.get("street_number")),
                "intersection": self.intersection.with_value(form.get("intersection")),
                "neighborhood": self.neighborhood.with_value(form.get("neighborhood")),
                "checklist": [
                    c.model_copy(update={"answered": c.question in answered}) for c in self.checklist
                ],
            }
        )

    @property
    def location_fields(self) -> list[tuple[str, str, FieldVM]]:
        return [
            ("street", "Calle", self.street),
            ("street_number", "Altura", self.street_number),
            ("intersection", "Intersección", self.intersection),
            ("neighborhood", "Barrio", self.neighborhood),
        ]
