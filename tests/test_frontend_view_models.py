"""frontend/view_models/: helpers de presentación y parseo de formularios (sin HTTP ni vistas)."""

from __future__ import annotations

from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import QueryDict
from django.utils.datastructures import MultiValueDict
from pydantic import ValidationError

from frontend.view_models import (
    MAX_UPLOAD_BYTES,
    CallCardFormVM,
    CallCardVM,
    FieldVM,
    SuggestionVM,
    TranscriptInputError,
    decode_text_upload,
    split_turns,
    transcript_from_submission,
)

TRANSCRIPT = "Operador: 911, ¿dónde es su urgencia? Llamante: Hay fuego en Av. Corrientes 1540."


def _post(**fields: str | list[str]) -> QueryDict:
    q = QueryDict(mutable=True)
    for key, value in fields.items():
        if isinstance(value, list):
            q.setlist(key, value)
        else:
            q[key] = value
    return q


def _files(upload: SimpleUploadedFile | None = None) -> MultiValueDict:
    return MultiValueDict({"transcript_file": [upload]} if upload else {})


# --------------------------------------------------- entrada de transcripción
class TestDecodeTextUpload:
    def test_utf8(self) -> None:
        assert decode_text_upload("Castañares".encode()) == "Castañares"

    def test_utf8_bom_is_stripped(self) -> None:
        assert decode_text_upload(b"\xef\xbb\xbf" + "Núñez".encode()) == "Núñez"

    def test_falls_back_to_cp1252(self) -> None:
        assert decode_text_upload("Castañares".encode("cp1252")) == "Castañares"

    def test_binary_is_rejected(self) -> None:
        with pytest.raises(TranscriptInputError, match="no parece ser de texto plano"):
            decode_text_upload(b"\x89PNG\x00\x00")


class TestTranscriptFromSubmission:
    def test_typed_text_is_stripped(self) -> None:
        assert transcript_from_submission(_post(transcript=f"  {TRANSCRIPT}\n"), _files()) == TRANSCRIPT

    def test_uploaded_file_wins_over_typed_text(self) -> None:
        upload = SimpleUploadedFile("llamada.txt", TRANSCRIPT.encode("cp1252"))
        result = transcript_from_submission(_post(transcript="otro texto escrito a mano"), _files(upload))
        assert result == TRANSCRIPT

    def test_empty_upload_falls_back_to_typed_text(self) -> None:
        upload = SimpleUploadedFile("vacio.txt", b"")
        assert transcript_from_submission(_post(transcript=TRANSCRIPT), _files(upload)) == TRANSCRIPT

    def test_too_large_upload_is_rejected(self) -> None:
        upload = SimpleUploadedFile("enorme.txt", b"a" * (MAX_UPLOAD_BYTES + 1))
        with pytest.raises(TranscriptInputError, match="supera el máximo de 200 KB"):
            transcript_from_submission(_post(), _files(upload))

    @pytest.mark.parametrize("typed", ["", "   ", "corto"])
    def test_too_short_is_rejected(self, typed: str) -> None:
        with pytest.raises(TranscriptInputError, match="demasiado corta"):
            transcript_from_submission(_post(transcript=typed), _files())


class TestSplitTurns:
    def test_splits_speakers_in_order(self) -> None:
        turns = split_turns(TRANSCRIPT)
        assert [(t.speaker, t.role) for t in turns] == [("Operador", "operador"), ("Llamante", "llamante")]
        assert turns[0].text == "911, ¿dónde es su urgencia?"
        assert turns[1].text == "Hay fuego en Av. Corrientes 1540."

    def test_operadora_and_case_insensitive_labels(self) -> None:
        turns = split_turns("OPERADORA: 107. llamante: mi mamá no respira")
        assert [(t.speaker, t.role) for t in turns] == [("Operadora", "operador"), ("Llamante", "llamante")]

    def test_text_without_labels_is_one_anonymous_turn(self) -> None:
        turns = split_turns("Hay un árbol caído sobre un auto.")
        assert len(turns) == 1
        assert (turns[0].speaker, turns[0].role) == ("", "otro")

    def test_empty_turns_are_dropped(self) -> None:
        assert [t.speaker for t in split_turns("Operador: Llamante: Hola, hay humo.")] == ["Llamante"]


# --------------------------------------------------------------- sugerencia
class TestFieldVM:
    def test_missing(self) -> None:
        field = FieldVM(value=None, evidence=None, grounded=False)
        assert (field.state, field.hint, field.display_value) == ("missing", "No mencionado: preguntar", "")

    def test_ungrounded_value_warns(self) -> None:
        field = FieldVM(value="Av. Santa Fe", evidence="Av. Santa Fe 3200", grounded=False)
        assert field.state == "warn"
        assert field.hint == "⚠ Sin evidencia literal: verificar"

    def test_grounded_value_quotes_evidence(self) -> None:
        field = FieldVM(value="Corrientes", evidence="Av. Corrientes 1540", grounded=True, normalized="Av. Corrientes")
        assert field.state == "ok"
        assert field.hint == '✓ "Av. Corrientes 1540"'
        assert field.display_value == "Av. Corrientes"

    def test_grounded_value_without_evidence_does_not_render_none(self) -> None:
        field = FieldVM(value="Thames", evidence=None, grounded=True)
        assert "None" not in field.hint

    def test_edited_state(self) -> None:
        field = FieldVM(value="Thames", evidence=None, grounded=False, edited=True)
        assert (field.state, field.hint) == ("edited", "✎ Editado por el operador")

    def test_with_value_unchanged_keeps_evidence(self) -> None:
        field = FieldVM(value="Corrientes", evidence="Av. Corrientes 1540", grounded=True, normalized="Av. Corrientes")
        assert field.with_value(" Av. Corrientes ") is field

    def test_with_value_changed_is_marked_edited(self) -> None:
        field = FieldVM(value="Corrientes", evidence="Av. Corrientes 1540", grounded=True)
        edited = field.with_value("Montevideo")
        assert (edited.value, edited.evidence, edited.grounded, edited.state) == ("Montevideo", None, False, "edited")

    def test_with_value_cleared_is_missing(self) -> None:
        field = FieldVM(value="Corrientes", evidence="Corrientes 1540", grounded=True)
        assert field.with_value("  ").state == "missing"


def _field(value: str | None, grounded: bool = True, normalized: str | None = None) -> dict[str, Any]:
    return {"value": value, "evidence": value, "grounded": grounded, "normalized": normalized}


@pytest.fixture
def suggestion() -> SuggestionVM:
    return SuggestionVM.model_validate(
        {
            "provider": "mock",
            "street": _field("Corrientes", normalized="Av. Corrientes"),
            "street_number": _field("1540"),
            "intersection": _field(None, grounded=False),
            "neighborhood": _field(None, grounded=False),
            "category": "INCENDIO_RESCATE",
            "subcategory": "Incendio en Comercio Gastronómico",
            "priority": "P1",
            "priority_rationale": "Personas atrapadas.",
            "checklist": [
                {"question": "¿Hay personas atrapadas?", "answered": True, "answer": "Sí", "grounded": True},
                {"question": "¿Hay garrafas?", "answered": False},
                {"question": "¿Hay linderos afectados?", "answered": False},
            ],
            "pre_arrival_instructions": ["No reingresar al local."],
            "risks": ["Grasa inflamada"],
            "suggested_resources": "1x Autobomba",
            "summary": "Fuego en pizzería.",
            "confidence": 0.8349,
        }
    )


class TestSuggestionVM:
    def test_confidence_pct(self, suggestion: SuggestionVM) -> None:
        assert suggestion.confidence_pct == 83

    def test_checklist_pending_first_is_stable(self, suggestion: SuggestionVM) -> None:
        assert [c.question for c in suggestion.checklist_pending_first] == [
            "¿Hay garrafas?",
            "¿Hay linderos afectados?",
            "¿Hay personas atrapadas?",
        ]

    def test_answered_count(self, suggestion: SuggestionVM) -> None:
        assert suggestion.answered_count == 1

    def test_location_summary_uses_normalized_street(self, suggestion: SuggestionVM) -> None:
        assert suggestion.location_summary == "Av. Corrientes 1540"

    def test_location_summary_without_street(self, suggestion: SuggestionVM) -> None:
        empty = suggestion.model_copy(
            update={"street": FieldVM(**_field(None, False)), "street_number": FieldVM(**_field(None, False))}
        )
        assert empty.location_summary == "Sin calle detectada"

    def test_location_fields_labels(self, suggestion: SuggestionVM) -> None:
        assert [(name, label) for name, label, _ in suggestion.location_fields] == [
            ("street", "Calle"),
            ("street_number", "Altura"),
            ("intersection", "Intersección"),
            ("neighborhood", "Barrio"),
        ]

    def test_with_operator_edits(self, suggestion: SuggestionVM) -> None:
        form = _post(
            priority="P2",
            category="INCENDIO_RESCATE",
            subcategory=" Incendio en cocina ",
            street="Av. Corrientes",
            street_number="1550",
            intersection="",
            neighborhood="San Nicolás",
            answered=["¿Hay garrafas?"],
        )
        edited = suggestion.with_operator_edits(form)

        assert (edited.priority, edited.subcategory) == ("P2", "Incendio en cocina")
        assert edited.street.state == "ok", "la calle sin cambios conserva su evidencia"
        assert edited.street_number.state == "edited" and edited.street_number.value == "1550"
        assert edited.neighborhood.state == "edited"
        assert edited.intersection.state == "missing"
        assert [c.question for c in edited.checklist if c.answered] == ["¿Hay garrafas?"]


# ------------------------------------------------------------ carta de llamada
class TestCallCardVM:
    def test_location_with_intersection(self) -> None:
        card = CallCardVM(
            id=1, created_at="2026-10-14T08:15:22Z", street="Av. Corrientes", street_number="1540",
            intersection="Montevideo", category="INCENDIO_RESCATE", subcategory="x", priority="P1",
        )
        assert card.location == "Av. Corrientes 1540 (Montevideo)"

    def test_location_street_only(self) -> None:
        card = CallCardVM(
            id=1, created_at="2026-10-14T08:15:22Z", street="Thames",
            category="DEFENSA_CIVIL", subcategory="x", priority="P2",
        )
        assert card.location == "Thames"

    def test_display_helpers(self) -> None:
        card = CallCardVM(
            id=1, created_at="2026-10-14T08:15:22Z", street="Thames", category="SERVICIOS_PUBLICOS",
            subcategory="x", priority="P1", answered_questions=["a"], pending_questions=["b", "c"], ai_confidence=0.834,
        )
        assert card.category_label == "Servicios publicos"
        assert card.confidence_pct == 83
        assert card.question_count == 3

    def test_confidence_is_optional(self) -> None:
        card = CallCardVM(
            id=1, created_at="2026-10-14T08:15:22Z", street="Thames", category="DEFENSA_CIVIL", subcategory="x", priority="P2",
        )
        assert card.confidence_pct is None


class TestCallCardFormVM:
    def test_from_post_parses_the_derive_form(self) -> None:
        form = _post(
            transcript=TRANSCRIPT,
            street="  Av. Corrientes ",
            street_number="1540",
            intersection="   ",
            category="INCENDIO_RESCATE",
            subcategory=" Incendio en Comercio Gastronómico ",
            priority="P1",
            questions=["¿Hay personas atrapadas?", "¿Hay garrafas?", "¿Hay linderos afectados?"],
            answered=["¿Hay garrafas?"],
            instructions=["No reingresar al local."],
            risks=["Grasa inflamada", "Gas"],
            operator_notes="",
            ai_confidence="0.83",
            ai_provider="mock",
        )
        card = CallCardFormVM.from_post(form)

        assert card.street == "Av. Corrientes"
        assert card.street_number == "1540"
        assert card.intersection is None and card.neighborhood is None and card.operator_notes is None
        assert card.subcategory == "Incendio en Comercio Gastronómico"
        assert card.answered_questions == ["¿Hay garrafas?"]
        assert card.pending_questions == ["¿Hay personas atrapadas?", "¿Hay linderos afectados?"]
        assert card.instructions_given == ["No reingresar al local."]
        assert card.risks == ["Grasa inflamada", "Gas"]
        assert card.ai_confidence == pytest.approx(0.83)
        assert card.ai_provider == "mock"

    def test_missing_confidence_is_none(self) -> None:
        card = CallCardFormVM.from_post(
            _post(transcript=TRANSCRIPT, street="Thames", category="DEFENSA_CIVIL", subcategory="x", priority="P2")
        )
        assert card.ai_confidence is None
        assert card.answered_questions == [] and card.pending_questions == []

    def test_empty_street_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CallCardFormVM.from_post(
                _post(transcript=TRANSCRIPT, street="   ", category="DEFENSA_CIVIL", subcategory="x", priority="P2")
            )
