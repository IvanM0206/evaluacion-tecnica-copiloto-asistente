"""CopilotService.analyze: fallback, control de preguntas contra el catálogo y warnings de grounding."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from services.copilot_service import CopilotService
from services.models import ChecklistAnswer, ExtractedField, Priority, RawExtraction, ReferenceCase
from services.providers import ExtractionContext, MockProvider, ProviderError

from tests.conftest import FakeCatalog

FIRE_ID = "SFX-REC-2026-001"  # pizzería en Av. Corrientes 1540 casi Montevideo


class FailingProvider:
    name = "anthropic"

    def extract(self, transcript: str, ctx: ExtractionContext) -> RawExtraction:
        raise ProviderError("Error del proveedor LLM (529)")


class TamperingProvider:
    """Corre el mock y deja que un test altere su salida (simula un LLM que se porta mal)."""

    name = "fake-llm"

    def __init__(self, tamper: Callable[[RawExtraction], RawExtraction]) -> None:
        self._tamper = tamper

    def extract(self, transcript: str, ctx: ExtractionContext) -> RawExtraction:
        return self._tamper(MockProvider().extract(transcript, ctx))


@pytest.fixture
def fire_transcript(case_by_id: dict[str, ReferenceCase]) -> str:
    return case_by_id[FIRE_ID].transcript


def _catalog_questions(cases: list[ReferenceCase]) -> set[str]:
    return {q for c in cases for q in c.mandatory_questions + c.pending_questions}


def test_mock_happy_path(fake_catalog: FakeCatalog, fire_transcript: str, reference_cases: list[ReferenceCase]) -> None:
    suggestion = CopilotService(fake_catalog, MockProvider()).analyze(fire_transcript)

    assert suggestion.provider == "mock"
    assert suggestion.street.grounded and suggestion.street.normalized == "Av. Corrientes"
    assert suggestion.priority == Priority.P1
    assert suggestion.pre_arrival_instructions, "pre-arrival instructions come from the anchor case"
    assert all(item.question in _catalog_questions(reference_cases) for item in suggestion.checklist)
    assert FIRE_ID not in {c.id for c in suggestion.similar_cases}, "leave-one-out"
    assert 0 <= suggestion.confidence <= 1


def test_provider_error_falls_back_to_mock_with_warning(fake_catalog: FakeCatalog, fire_transcript: str) -> None:
    suggestion = CopilotService(fake_catalog, FailingProvider()).analyze(fire_transcript)

    assert suggestion.provider == "mock (fallback)"
    assert suggestion.warnings[0] == (
        "Proveedor IA no disponible (Error del proveedor LLM (529)). Se usó el modo reglas."
    )
    assert suggestion.street.value == "Av. Corrientes"


def test_invented_checklist_questions_are_discarded(
    fake_catalog: FakeCatalog, fire_transcript: str, reference_cases: list[ReferenceCase]
) -> None:
    invented = "¿Cuál es el signo del zodíaco del llamante?"

    def add_invented_question(raw: RawExtraction) -> RawExtraction:
        extra = ChecklistAnswer(question=invented, answered=True, answer="Leo", evidence="pizzería")
        return raw.model_copy(update={"checklist": [*raw.checklist, extra]})

    suggestion = CopilotService(fake_catalog, TamperingProvider(add_invented_question)).analyze(fire_transcript)

    questions = [item.question for item in suggestion.checklist]
    assert invented not in questions
    assert questions and set(questions) <= _catalog_questions(reference_cases)
    assert "Se descartaron 1 preguntas no pertenecientes al protocolo." in suggestion.warnings


def test_ungrounded_answer_is_flagged(fake_catalog: FakeCatalog, fire_transcript: str) -> None:
    def answer_everything_with_made_up_evidence(raw: RawExtraction) -> RawExtraction:
        fake = [
            a.model_copy(update={"answered": True, "answer": "Sí", "evidence": "nos dijo que había tres heridos graves en el primer piso"})
            for a in raw.checklist
        ]
        return raw.model_copy(update={"checklist": fake})

    suggestion = CopilotService(fake_catalog, TamperingProvider(answer_everything_with_made_up_evidence)).analyze(
        fire_transcript
    )
    assert suggestion.checklist
    assert all(item.answered and not item.grounded for item in suggestion.checklist)


def test_ungrounded_street_produces_warning(fake_catalog: FakeCatalog, fire_transcript: str) -> None:
    def invent_street(raw: RawExtraction) -> RawExtraction:
        return raw.model_copy(update={"street": ExtractedField(value="Av. Santa Fe", evidence="Av. Santa Fe 3200")})

    suggestion = CopilotService(fake_catalog, TamperingProvider(invent_street)).analyze(fire_transcript)

    assert suggestion.street.value == "Av. Santa Fe"
    assert not suggestion.street.grounded
    assert "La calle sugerida no figura literalmente en el relato: verificar." in suggestion.warnings


def test_missing_location_produces_warnings(fake_catalog: FakeCatalog) -> None:
    transcript = "Operador: 911. Llamante: Hay mucho humo negro saliendo de una casa, manden bomberos ya."
    suggestion = CopilotService(fake_catalog, MockProvider()).analyze(transcript)

    assert suggestion.street.value is None and not suggestion.street.grounded
    assert "No se detectó la calle: confirmar dirección con el llamante." in suggestion.warnings
    assert "Falta altura o intersección para ubicar el hecho." in suggestion.warnings


def test_priority_differing_from_anchor_is_warned(fake_catalog: FakeCatalog, fire_transcript: str) -> None:
    def downgrade(raw: RawExtraction) -> RawExtraction:
        return raw.model_copy(update={"priority": Priority.P4})

    suggestion = CopilotService(fake_catalog, TamperingProvider(downgrade)).analyze(fire_transcript)
    assert any(w.startswith("La prioridad sugerida (P4) difiere del caso de referencia") for w in suggestion.warnings)


def test_indexes_are_built_lazily_once(fake_catalog: FakeCatalog, fire_transcript: str) -> None:
    service = CopilotService(fake_catalog, MockProvider())
    assert service._retriever is None and service._gazetteer is None
    service.analyze(fire_transcript)
    retriever = service.retriever
    service.analyze(fire_transcript)
    assert service.retriever is retriever


def test_value_not_contained_in_its_evidence_is_not_grounded(fake_catalog: FakeCatalog) -> None:
    # Un LLM que se porta mal cita un fragmento real pero informa otro número.
    transcript = "Operador: 911. Llamante: Hay humo saliendo de un local en Corrientes al 1234."

    def wrong_number(raw: RawExtraction) -> RawExtraction:
        return raw.model_copy(update={"street_number": ExtractedField(value="1243", evidence="Corrientes al 1234")})

    suggestion = CopilotService(fake_catalog, TamperingProvider(wrong_number)).analyze(transcript)
    assert suggestion.street_number.value == "1243"
    assert not suggestion.street_number.grounded


def test_value_found_in_transcript_without_evidence_uses_itself_as_evidence(fake_catalog: FakeCatalog) -> None:
    transcript = "Operador: 911. Llamante: Hay humo saliendo de un local en Corrientes al 1234."

    def no_evidence(raw: RawExtraction) -> RawExtraction:
        return raw.model_copy(update={"street_number": ExtractedField(value="1234", evidence=None)})

    suggestion = CopilotService(fake_catalog, TamperingProvider(no_evidence)).analyze(transcript)
    assert suggestion.street_number.grounded
    assert suggestion.street_number.evidence == "1234"
