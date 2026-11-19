"""Providers de extracción: reglas del mock determinista y mapeo de errores del adaptador de Anthropic."""

from __future__ import annotations

import pytest

from services.models import Category, Priority, RawExtraction, ReferenceCase
from services.nlp.retrieval import CaseRetriever
from services.providers import ExtractionContext, MockProvider, ProviderError


def _context_for(transcript: str, cases: list[ReferenceCase]) -> ExtractionContext:
    similar = CaseRetriever(cases).search(transcript, k=5)
    questions = [q for c, _ in similar[:1] for q in c.mandatory_questions]
    return ExtractionContext(similar_cases=similar, candidate_questions=questions)


# --------------------------------------------------------------------- mock
class TestMockProvider:
    def test_structure_fire_at_corrientes(self, case_by_id: dict[str, ReferenceCase], reference_cases: list[ReferenceCase]) -> None:
        transcript = case_by_id["SFX-REC-2026-001"].transcript
        raw = MockProvider().extract(transcript, _context_for(transcript, reference_cases))

        assert raw.street.value == "Av. Corrientes"
        assert raw.street_number.value == "1540"
        assert raw.street.evidence and raw.street.evidence in transcript
        assert raw.intersection.value == "Montevideo"
        assert raw.category == Category.INCENDIO_RESCATE
        assert raw.priority == Priority.P1

    def test_medical_emergency_at_cabildo(self, case_by_id: dict[str, ReferenceCase], reference_cases: list[ReferenceCase]) -> None:
        transcript = case_by_id["SFX-REC-2026-010"].transcript
        raw = MockProvider().extract(transcript, _context_for(transcript, reference_cases))

        assert raw.street.value == "Cabildo"
        assert raw.street_number.value == "3700"
        assert raw.category == Category.EMERGENCIA_MEDICA
        assert raw.priority == Priority.P2

    def test_checklist_answers_every_candidate_question(self, case_by_id: dict[str, ReferenceCase], reference_cases: list[ReferenceCase]) -> None:
        transcript = case_by_id["SFX-REC-2026-001"].transcript
        ctx = _context_for(transcript, reference_cases)
        raw = MockProvider().extract(transcript, ctx)
        assert [a.question for a in raw.checklist] == ctx.candidate_questions

    def test_red_flag_escalates_to_p1(self) -> None:
        transcript = "Operador: 107. Llamante: Mi papá se cayó en la cocina y no respira, está en Thames 1900."
        raw = MockProvider().extract(transcript, ExtractionContext(similar_cases=[], candidate_questions=[]))
        assert raw.priority == Priority.P1
        assert "no respira" in raw.priority_rationale
        assert raw.priority_rationale.startswith("Escalado a P1")

    def test_without_reference_or_red_flag_defaults_to_p3(self) -> None:
        transcript = "Operador: 147. Llamante: Hay un semáforo apagado en Thames 1900 hace un rato."
        raw = MockProvider().extract(transcript, ExtractionContext(similar_cases=[], candidate_questions=[]))
        assert raw.priority == Priority.P3
        assert raw.priority_rationale == "Sin referencia."
        assert raw.subcategory == "Sin subcategoría de referencia"

    def test_street_mentioned_by_operator_is_ignored(self) -> None:
        transcript = "Operador: ¿Es en Corrientes 1500? Llamante: No, estoy en Thames 1900."
        raw = MockProvider().extract(transcript, ExtractionContext(similar_cases=[], candidate_questions=[]))
        assert (raw.street.value, raw.street_number.value) == ("Thames", "1900")

    def test_espuma_en_la_boca_is_not_a_neighbourhood(self) -> None:
        transcript = "Operador: 107. Llamante: Está convulsionando y tiene espuma en la boca, vivimos en Palermo."
        raw = MockProvider().extract(transcript, ExtractionContext(similar_cases=[], candidate_questions=[]))
        assert raw.neighborhood.value == "Palermo"

    def test_question_answered_by_caller_sentence(self) -> None:
        transcript = "Operador: ¿Qué pasa? Llamante: Hay una persona atrapada adentro del auto, no puede salir."
        answer = MockProvider.answer_question("¿Hay personas atrapadas?", transcript)
        assert answer.answered
        assert answer.evidence and "atrapada" in answer.evidence

    def test_unrelated_question_is_pending(self) -> None:
        transcript = "Operador: ¿Qué pasa? Llamante: Hay una persona atrapada adentro del auto."
        answer = MockProvider.answer_question("¿Hay derrame de combustible?", transcript)
        assert not answer.answered and answer.answer is None
