"""services.prompts: secciones componibles y el prompt de extracción."""

from __future__ import annotations

from services.models import ReferenceCase
from services.prompts import EXTRACTION_PROMPT, PromptSection, build_extraction_user_message


def test_extraction_prompt_is_composed_of_named_sections() -> None:
    assert EXTRACTION_PROMPT.section_keys == (
        "role", "grounding", "classification", "protocol_checklist", "dispatch_summary",
    )
    system = EXTRACTION_PROMPT.system
    assert "EXTRAER, no inventar" in system
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
