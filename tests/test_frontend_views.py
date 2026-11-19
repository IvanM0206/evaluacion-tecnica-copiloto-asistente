"""Vistas del front con un ApiClient falso: el flujo del panel sin tocar la capa API."""

from __future__ import annotations

from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from frontend import views
from frontend.client import ApiError
from frontend.view_models import HealthVM, SampleVM, SuggestionVM

TRANSCRIPT = (
    "Operador: Emergencias, ¿dónde es? Llamante: En Thames 1900, entre Nicaragua y Costa Rica. "
    "Rompieron un caño y hay olor a gas en las casas."
)
QUESTIONS = ["¿Hay personas descompuestas?", "¿Se escucha el escape de gas?"]


def _suggestion() -> SuggestionVM:
    def field(value: str | None) -> dict[str, Any]:
        return {"value": value, "evidence": value, "grounded": value is not None}

    return SuggestionVM.model_validate(
        {
            "provider": "mock",
            "street": field("Thames"),
            "street_number": field("1900"),
            "intersection": field("Nicaragua y Costa Rica"),
            "neighborhood": field(None),
            "category": "SERVICIOS_PUBLICOS",
            "subcategory": "Fuga de gas",
            "priority": "P1",
            "priority_rationale": "Escalado a P1 por 'olor a gas'.",
            "checklist": [
                {"question": QUESTIONS[0], "answered": False},
                {"question": QUESTIONS[1], "answered": True, "answer": "Sí", "evidence": "olor a gas", "grounded": True},
            ],
            "pre_arrival_instructions": ["No accione interruptores.", "Abra puertas y ventanas."],
            "risks": ["Explosión"],
            "suggested_resources": "Bomberos y empresa distribuidora",
            "summary": "Fuga de gas en vereda.",
            "confidence": 0.9,
        }
    )


class FakeApiClient:
    """Reemplaza a frontend.client.ApiClient; registra lo que envían las vistas."""

    analyze_calls: list[str] = []
    fail_analyze = False
    fail_health = False

    def health(self) -> HealthVM:
        if self.fail_health:
            raise ApiError("No se pudo contactar la API (ConnectError)")
        return HealthVM(status="ok", provider="mock", catalog_size=30)

    def sample(self, sample_id: str) -> SampleVM:
        if sample_id != views.DEMO_SAMPLE_ID:
            raise ApiError("La API respondió 404")
        return SampleVM(id=sample_id, label="demo", transcript=TRANSCRIPT)

    def analyze(self, transcript: str) -> SuggestionVM:
        if self.fail_analyze:
            raise ApiError("No se pudo contactar la API")
        FakeApiClient.analyze_calls.append(transcript)
        return _suggestion()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, db: None) -> Client:
    FakeApiClient.analyze_calls = []
    FakeApiClient.fail_analyze = False
    FakeApiClient.fail_health = False
    monkeypatch.setattr(views, "ApiClient", FakeApiClient)
    return Client()


def _analyze(client: Client, **data: Any) -> None:
    response = client.post("/analizar/", {"origin": "landing", **data})
    assert response.status_code == 302 and response["Location"] == "/cargando/"


class TestLanding:
    def test_renders_upload_card(self, client: Client) -> None:
        html = client.get("/").content.decode()
        assert "Nueva transcripción" in html
        assert 'name="transcript_file"' in html
        assert f"?sample={views.DEMO_SAMPLE_ID}" in html

    def test_sample_prefills_textarea(self, client: Client) -> None:
        html = client.get(f"/?sample={views.DEMO_SAMPLE_ID}").content.decode()
        assert "En Thames 1900" in html

    def test_unknown_sample_shows_error(self, client: Client) -> None:
        html = client.get("/?sample=NOPE").content.decode()
        assert "No se pudo cargar la plantilla" in html


class TestAnalyzeFlow:
    def test_typed_transcript_goes_through_loader_to_workspace(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        loading = client.get("/cargando/").content.decode()
        assert 'http-equiv="refresh"' in loading and "/analisis/" in loading

        html = client.get("/analisis/").content.decode()
        assert FakeApiClient.analyze_calls == [TRANSCRIPT]
        assert "Sugerencia del copiloto" in html
        assert '<span class="speaker">Llamante</span>' in html

    def test_suggestion_is_cached_in_session(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        client.get("/analisis/")
        client.get("/analisis/")
        assert len(FakeApiClient.analyze_calls) == 1

    def test_uploaded_file_wins_over_typed_text(self, client: Client) -> None:
        upload = SimpleUploadedFile("llamada.txt", TRANSCRIPT.encode("utf-8"), content_type="text/plain")
        _analyze(client, transcript="texto que se ignora", transcript_file=upload)
        client.get("/analisis/")
        assert FakeApiClient.analyze_calls == [TRANSCRIPT]

    def test_short_transcript_returns_to_landing_with_draft(self, client: Client) -> None:
        response = client.post("/analizar/", {"origin": "landing", "transcript": "corto"}, follow=True)
        html = response.content.decode()
        assert "demasiado corta" in html
        assert "corto</textarea>" in html

    def test_short_transcript_from_workspace_stays_in_workspace_with_draft(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        client.get("/analisis/")
        response = client.post("/analizar/", {"origin": "workspace", "transcript": "corto"})
        assert response["Location"] == "/analisis/"
        html = client.get("/analisis/").content.decode()
        assert 'id="mode-new" class="mode-radio" checked' in html
        assert "corto</textarea>" in html

    def test_failed_new_analysis_keeps_the_previous_one(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        client.get("/analisis/")
        FakeApiClient.fail_analyze = True
        other = "Operador: 911. Llamante: Hay un choque en Rivadavia al 5000, un herido."
        _analyze(client, transcript=other)
        response = client.get("/analisis/", follow=True)
        html = response.content.decode()
        assert response.redirect_chain[-1][0] == "/analisis/"
        assert "Error al analizar" in html
        assert "En Thames 1900" in html  # la transcripción anterior se sigue mostrando a la izquierda
        assert f"{other}</textarea>" in html  # el texto nuevo vuelve en "Nueva transcripción"

    def test_api_error_goes_back_to_landing_keeping_the_transcript(self, client: Client) -> None:
        FakeApiClient.fail_analyze = True
        _analyze(client, transcript=TRANSCRIPT)
        html = client.get("/analisis/", follow=True).content.decode()
        assert "Error al analizar" in html
        assert "En Thames 1900" in html

    @pytest.mark.parametrize("url", ["/cargando/", "/analisis/"])
    def test_without_analysis_redirects_home(self, client: Client, url: str) -> None:
        assert client.get(url)["Location"] == "/"

    def test_sample_in_workspace_opens_new_transcript_pane(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        html = client.get(f"/analisis/?sample={views.DEMO_SAMPLE_ID}").content.decode()
        assert 'id="mode-new" class="mode-radio" checked' in html


class TestWorkspace:
    def test_renders_the_suggestion_read_only(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        html = client.get("/analisis/").content.decode()
        assert '<span class="badge P1">P1</span>' in html
        assert "SERVICIOS_PUBLICOS" in html and "Fuga de gas" in html
        assert "Thames" in html and "1900" in html
        assert "No mencionado: preguntar" in html  # barrio no mencionado
        assert "No accione interruptores." in html
        assert "1/2 respondidas" in html
        assert "<form" not in html.split("Sugerencia del copiloto")[1], "el panel de sugerencia es de solo lectura"

    def test_pending_questions_are_listed_first(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        html = client.get("/analisis/").content.decode()
        assert html.index(QUESTIONS[0]) < html.index(QUESTIONS[1])


class TestHeader:
    def test_shows_provider_status(self, client: Client) -> None:
        assert "Proveedor: mock · 30 casos" in client.get("/").content.decode()

    def test_api_down_is_reported_without_breaking_the_page(self, client: Client) -> None:
        FakeApiClient.fail_health = True
        response = client.get("/")
        assert response.status_code == 200
        assert "No se pudo contactar la API" in response.content.decode()
