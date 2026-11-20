"""services.prompts: secciones componibles y el prompt de extracción."""

from __future__ import annotations

from services.models import MAX_SUGGESTED_QUESTIONS, RawExtraction, ReferenceCase
from services.prompts import EXTRACTION_PROMPT, PromptSection, build_extraction_user_message


def test_extraction_prompt_is_composed_of_named_sections() -> None:
    assert EXTRACTION_PROMPT.section_keys == (
        "role", "grounding", "classification", "protocol_checklist", "suggested_questions", "dispatch_summary",
    )
    system = EXTRACTION_PROMPT.system
    assert "EXTRAER, no inventar" in system
    assert f"hasta {MAX_SUGGESTED_QUESTIONS} preguntas" in system
    assert "\n\n\n" not in system


def test_templates_can_be_extended_for_new_skills_or_agents() -> None:
    triage = EXTRACTION_PROMPT.with_sections(PromptSection("triage", "Priorizá P1."), name="triage", version="1")
    assert triage.name == "triage" and triage.section_keys[-1] == "triage"
    assert triage.system.endswith("Priorizá P1.")
    assert EXTRACTION_PROMPT.section_keys[-1] == "dispatch_summary", "el template base no se modifica"


def test_user_message_carries_cases_questions_and_transcript(reference_cases: list[ReferenceCase]) -> None:
    case = reference_cases[0]
    message = build_extraction_user_message("Llamante: humo en la cocina", [(case, 0.5)], ["¿Hay atrapados?"])
    assert f"<caso id='{case.id}'>" in message
    assert f"categoria: {case.category}" in message and case.street in message
    assert "- ¿Hay atrapados?" in message
    assert message.endswith("<transcripcion>\nLlamante: humo en la cocina\n</transcripcion>")


def test_schema_exposes_suggested_questions_to_the_llm() -> None:
    schema = RawExtraction.model_json_schema()
    assert schema["properties"]["suggested_questions"]["type"] == "array"
    assert RawExtraction.model_validate(_minimal()).suggested_questions == [], "opcional para los providers"


def _minimal() -> dict[str, object]:
    empty = {"value": None, "evidence": None}
    return {
        "street": empty, "street_number": empty, "intersection": empty, "neighborhood": empty,
        "category": "DEFENSA_CIVIL", "subcategory": "x", "priority": "P3", "priority_rationale": "x",
        "checklist": [], "risks": [], "summary": "x",
    }
