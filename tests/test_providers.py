"""Providers de extracción: reglas del mock determinista y mapeo de errores del adaptador de Anthropic."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2  # el stack HTTP del SDK de anthropic (no el `httpx` que usa el front)
import pytest

from services.models import Category, Priority, RawExtraction, ReferenceCase
from services.nlp.retrieval import CaseRetriever
from services.prompts import EXTRACTION_PROMPT
from services.providers import ExtractionContext, MockProvider, ProviderError
from services.providers.anthropic_provider import AnthropicProvider


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


# ---------------------------------------------------------------- anthropic
VALID_EXTRACTION: dict[str, Any] = {
    "street": {"value": "Thames", "evidence": "Thames 1900"},
    "street_number": {"value": "1900", "evidence": "Thames 1900"},
    "intersection": {"value": None, "evidence": None},
    "neighborhood": {"value": None, "evidence": None},
    "category": "DEFENSA_CIVIL",
    "subcategory": "Derrumbe",
    "priority": "P1",
    "priority_rationale": "Personas atrapadas.",
    "checklist": [],
    "risks": [],
    "summary": "Derrumbe en Thames 1900.",
}

EMPTY_CTX = ExtractionContext(similar_cases=[], candidate_questions=["¿Hay personas atrapadas?"])
TRANSCRIPT = "Operador: 911. Llamante: Se derrumbó una pared en Thames 1900."


class FakeMessages:
    """Reemplaza a `client.beta.messages`: devuelve una respuesta armada o lanza."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def _fake_client(outcome: Any) -> tuple[Any, FakeMessages]:
    messages = FakeMessages(outcome)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def _response(stop_reason: str = "end_turn", parsed: RawExtraction | None = None) -> SimpleNamespace:
    return SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed)


_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class TestAnthropicProviderWithFakeClient:
    def test_returns_parsed_output_and_sends_schema_and_transcript(self) -> None:
        expected = RawExtraction.model_validate(VALID_EXTRACTION)
        client, messages = _fake_client(_response(parsed=expected))
        result = AnthropicProvider(model="test-model", client=client).extract(TRANSCRIPT, EMPTY_CTX)

        assert result == expected
        call = messages.calls[0]
        assert call["model"] == "test-model"
        assert call["output_format"] is RawExtraction
        assert call["output_config"] == {"effort": "low"}
        assert call["max_tokens"] == 16_000
        assert call["system"] == EXTRACTION_PROMPT.system
        assert TRANSCRIPT in call["messages"][0]["content"]
        assert "¿Hay personas atrapadas?" in call["messages"][0]["content"]

    @pytest.mark.parametrize(
        ("error", "message"),
        [
            (
                anthropic.RateLimitError("slow down", response=httpx2.Response(429, request=_REQUEST), body=None),
                "Rate limit",
            ),
            (
                anthropic.InternalServerError("boom", response=httpx2.Response(500, request=_REQUEST), body=None),
                "(500)",
            ),
            (
                anthropic.AuthenticationError("bad key", response=httpx2.Response(401, request=_REQUEST), body=None),
                "(401)",
            ),
            (anthropic.APIConnectionError(request=_REQUEST), "Sin conexión"),
            (anthropic.APITimeoutError(request=_REQUEST), "Sin conexión"),
        ],
    )
    def test_api_errors_become_provider_errors(self, error: Exception, message: str) -> None:
        client, _ = _fake_client(error)
        with pytest.raises(ProviderError, match=message.replace("(", r"\(").replace(")", r"\)")):
            AnthropicProvider(model="m", client=client).extract(TRANSCRIPT, EMPTY_CTX)

    @pytest.mark.parametrize(
        ("response", "message"),
        [
            (_response(stop_reason="refusal"), "rechazó"),
            (_response(stop_reason="max_tokens"), "truncada"),
            (_response(parsed=None), "JSON válido"),
        ],
    )
    def test_unusable_responses_become_provider_errors(self, response: SimpleNamespace, message: str) -> None:
        client, _ = _fake_client(response)
        with pytest.raises(ProviderError, match=message):
            AnthropicProvider(model="m", client=client).extract(TRANSCRIPT, EMPTY_CTX)


def _sdk_client(text: str, stop_reason: str = "end_turn", status: int = 200) -> anthropic.Anthropic:
    """Un cliente real del SDK con el transporte HTTP mockeado en el proceso (sin red)."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        if status != 200:
            return httpx2.Response(status, json={"type": "error", "error": {"type": "api_error", "message": "x"}})
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "test-model",
                "content": [{"type": "text", "text": text}],
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    return anthropic.Anthropic(
        api_key="test-key", max_retries=0, http_client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )


class TestAnthropicProviderWithMockedTransport:
    """De punta a punta por el camino de parseo real del SDK, para atrapar lo que los fakes esconden."""

    def test_valid_json_is_parsed(self) -> None:
        provider = AnthropicProvider(model="m", client=_sdk_client(json.dumps(VALID_EXTRACTION)))
        assert provider.extract(TRANSCRIPT, EMPTY_CTX).street.value == "Thames"

    def test_http_500_becomes_provider_error(self) -> None:
        provider = AnthropicProvider(model="m", client=_sdk_client("", status=500))
        with pytest.raises(ProviderError, match="500"):
            provider.extract(TRANSCRIPT, EMPTY_CTX)

    def test_malformed_json_becomes_provider_error(self) -> None:
        provider = AnthropicProvider(model="m", client=_sdk_client('{"street": "no es el esquema"'))
        with pytest.raises(ProviderError):
            provider.extract(TRANSCRIPT, EMPTY_CTX)

    def test_truncated_response_becomes_provider_error(self) -> None:
        truncated = json.dumps(VALID_EXTRACTION)[:60]
        provider = AnthropicProvider(model="m", client=_sdk_client(truncated, stop_reason="max_tokens"))
        with pytest.raises(ProviderError, match="truncada"):
            provider.extract(TRANSCRIPT, EMPTY_CTX)

    def test_request_body_sent_by_the_real_sdk(self) -> None:
        """Lo que realmente viaja: effort y el JSON schema comparten `output_config`, el fallback
        del lado del servidor está activado y el prompt sale de services.prompts."""
        seen: list[httpx2.Request] = []
        inner = _sdk_client(json.dumps(VALID_EXTRACTION))
        transport = inner._client._transport  # el MockTransport que arma _sdk_client

        def spy(request: httpx2.Request) -> httpx2.Response:
            seen.append(request)
            return transport.handle_request(request)

        client = anthropic.Anthropic(
            api_key="test-key", max_retries=0, http_client=httpx2.Client(transport=httpx2.MockTransport(spy))
        )
        AnthropicProvider(model="claude-opus-5-5", client=client).extract(TRANSCRIPT, EMPTY_CTX)

        body = json.loads(seen[0].content)
        assert body["output_config"]["effort"] == "low"
        assert body["output_config"]["format"]["type"] == "json_schema"
        assert "street" in body["output_config"]["format"]["schema"]["properties"]
        assert body["fallbacks"] == "default"
        assert "server-side-fallback-2026-07-01" in seen[0].headers["anthropic-beta"]
        assert body["system"] == EXTRACTION_PROMPT.system
        assert body["max_tokens"] == 16_000
