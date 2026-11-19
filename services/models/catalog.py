"""Catálogo de referencia: casos mapeados desde backend.Incident, incidentes sintéticos y ejemplos de demo."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.choices import Category, Priority


class ReferenceCase(BaseModel):
    id: str
    source: str
    origin: str
    category: Category
    subcategory: str
    priority: Priority
    transcript: str
    street: str
    street_number: str
    intersection: str
    neighborhood: str
    mandatory_questions: list[str]
    pending_questions: list[str]
    pre_arrival_instructions: str
    risks: list[str]
    resources: str
    notes: str


class IncidentCreate(BaseModel):
    """Incidente sintético/hipotético agregado al catálogo de referencia en tiempo de ejecución.
    """

    id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    origin: str = "SINTETICO"
    category: Category
    subcategory: str = Field(min_length=1, max_length=160)
    priority: Priority
    transcript: str = Field(min_length=10)
    street: str = ""
    street_number: str = ""
    intersection: str = ""
    neighborhood: str = ""
    mandatory_questions: list[str] = Field(default_factory=list)
    answered_questions: list[str] = Field(default_factory=list)
    pending_questions: list[str] = Field(default_factory=list)
    pre_arrival_instructions: str = ""
    risks: list[str] = Field(default_factory=list)
    resources: str = ""
    notes: str = ""


class SampleTranscript(BaseModel):
    id: str
    label: str
    transcript: str
