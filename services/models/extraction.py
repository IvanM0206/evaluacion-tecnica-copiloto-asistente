"""Salida cruda del provider (mock o LLM).

Plana a propósito para que sirva como JSON schema de structured outputs del LLM.
Cada afirmación lleva una cita de evidencia de la llamada.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.choices import Category, Priority

# Preguntas extra (fuera del protocolo) que puede proponer un LLM; más que esto es ruido bajo estrés.
MAX_SUGGESTED_QUESTIONS = 3


class ExtractedField(BaseModel):
    value: str | None = Field(None, description="Valor extraído, o null si no se menciona.")
    evidence: str | None = Field(
        None, description="Fragmento textual literal de la transcripción que respalda el valor."
    )


class ChecklistAnswer(BaseModel):
    question: str = Field(description="Pregunta de protocolo, copiada tal cual de la lista provista.")
    answered: bool
    answer: str | None = Field(None, description="Respuesta breve según el relato.")
    evidence: str | None = Field(None, description="Fragmento literal de la transcripción.")


class RawExtraction(BaseModel):
    street: ExtractedField
    street_number: ExtractedField
    intersection: ExtractedField
    neighborhood: ExtractedField
    category: Category
    subcategory: str
    priority: Priority
    priority_rationale: str
    checklist: list[ChecklistAnswer]
    risks: list[str]
    summary: str = Field(description="Resumen operativo de una o dos líneas para el despachador.")
    suggested_questions: list[str] = Field(
        default_factory=list,
        description=(
            f"Hasta {MAX_SUGGESTED_QUESTIONS} preguntas relevantes que el relato no responde y que no "
            "están en la lista de protocolo. Lista vacía si no hay ninguna."
        ),
    )
