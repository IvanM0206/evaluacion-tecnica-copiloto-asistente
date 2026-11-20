"""Tarea de extracción: una llamada que completa `RawExtraction` a partir de una transcripción."""

from __future__ import annotations

from collections.abc import Sequence

from services.models import ReferenceCase
from services.prompts.base import PromptTemplate
from services.prompts.sections import (
    CLASSIFICATION,
    DISPATCH_SUMMARY,
    GROUNDING,
    PROTOCOL_CHECKLIST,
    ROLE,
    SUGGESTED_QUESTIONS,
)

EXTRACTION_PROMPT = PromptTemplate(
    name="extraction",
    version="2",
    sections=(ROLE, GROUNDING, CLASSIFICATION, PROTOCOL_CHECKLIST, SUGGESTED_QUESTIONS, DISPATCH_SUMMARY),
)


def render_reference_cases(similar_cases: Sequence[tuple[ReferenceCase, float]]) -> str:
    """Bloque few-shot: los casos del catálogo más parecidos, con su ground truth."""
    return "\n".join(
        f"<caso id='{case.id}'>\n"
        f"transcripcion: {case.transcript}\n"
        f"categoria: {case.category} | subcategoria: {case.subcategory} | prioridad: {case.priority}\n"
        f"ubicacion: {case.street} {case.street_number} ({case.intersection}) - {case.neighborhood}\n"
        f"</caso>"
        for case, _score in similar_cases
    )


def build_extraction_user_message(
    transcript: str,
    similar_cases: Sequence[tuple[ReferenceCase, float]],
    protocol_questions: Sequence[str],
) -> str:
    questions = "\n".join(f"- {q}" for q in protocol_questions)
    return (
        f"<casos_de_referencia>\n{render_reference_cases(similar_cases)}\n</casos_de_referencia>\n\n"
        f"<preguntas_protocolo>\n{questions}\n</preguntas_protocolo>\n\n"
        f"<transcripcion>\n{transcript}\n</transcripcion>"
    )
