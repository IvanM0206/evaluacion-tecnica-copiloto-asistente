"""Vistas del front con un ApiClient falso: el flujo del panel sin tocar la capa API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from frontend import views
from frontend.client import ApiError
from frontend.view_models import CallCardFormVM, CallCardVM, HealthVM, SampleVM, SuggestionVM

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
    derived: list[CallCardFormVM] = []
    stored_cards: list[CallCardVM] = []
    fail_analyze = False
    fail_health = False
    fail_derive = False
    fail_cards = False

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

    def cards(self) -> list[CallCardVM]:
        if self.fail_cards:
            raise ApiError("La API respondió 500")
        return FakeApiClient.stored_cards

    def derive_card(self, card: CallCardFormVM) -> CallCardVM:
        if self.fail_derive:
            raise ApiError("La API respondió 500")
        FakeApiClient.derived.append(card)
        return CallCardVM(
            id=7, created_at=datetime(2026, 11, 18, 10, 0), street=card.street,
            category=card.category, subcategory=card.subcategory, priority=card.priority,
        )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, db: None) -> Client:
    FakeApiClient.analyze_calls = []
    FakeApiClient.derived = []
    FakeApiClient.stored_cards = []
    FakeApiClient.fail_analyze = False
    FakeApiClient.fail_health = False
    FakeApiClient.fail_derive = False
    FakeApiClient.fail_cards = False
    monkeypatch.setattr(views, "ApiClient", FakeApiClient)
    return Client()


def _analyze(client: Client, **data: Any) -> None:
    response = client.post("/analizar/", {"origin": "landing", **data})
    assert response.status_code == 302 and response["Location"] == "/cargando/"


def _derive_form(**overrides: Any) -> dict[str, Any]:
    form: dict[str, Any] = {
        "transcript": TRANSCRIPT, "priority": "P1", "category": "SERVICIOS_PUBLICOS",
        "subcategory": "Fuga de gas", "street": "Thames", "street_number": "1900",
        "intersection": "Nicaragua y Costa Rica", "neighborhood": "", "questions": QUESTIONS,
        "answered": [QUESTIONS[1]], "ai_confidence": "0.9", "ai_provider": "mock",
    }
    return {**form, **overrides}


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
    def test_renders_the_suggestion_as_an_editable_derive_form(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        html = client.get("/analisis/").content.decode()
        assert 'action="/derivar/"' in html
        assert '<select name="priority" class="P1">' in html and "<option selected>P1</option>" in html
        assert "<option selected>SERVICIOS_PUBLICOS</option>" in html
        assert 'name="street" value="Thames"' in html and 'name="street_number" value="1900"' in html
        assert "No mencionado: preguntar" in html  # barrio no mencionado
        assert 'name="instructions" value="No accione interruptores."' in html
        assert "1/2 respondidas" in html
        assert "Derivar Carta de Llamada" in html

    def test_pending_questions_are_listed_first(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        html = client.get("/analisis/").content.decode()
        assert html.index(QUESTIONS[0]) < html.index(QUESTIONS[1])


class TestHeader:
    @pytest.mark.parametrize("url", ["/", "/cartas/"])
    def test_nav_links_to_panel_and_cards(self, client: Client, url: str) -> None:
        html = client.get(url).content.decode()
        assert 'class="topnav"' in html
        assert 'href="/cartas/"' in html and ">Cartas derivadas</a>" in html

    def test_active_item_follows_the_screen(self, client: Client) -> None:
        assert 'href="/" class="active"' in client.get("/").content.decode()
        assert 'href="/cartas/" class="active"' in client.get("/cartas/").content.decode()

    def test_shows_provider_status(self, client: Client) -> None:
        assert "Proveedor: mock · 30 casos" in client.get("/").content.decode()

    def test_api_down_is_reported_without_breaking_the_page(self, client: Client) -> None:
        FakeApiClient.fail_health = True
        response = client.get("/")
        assert response.status_code == 200
        assert "No se pudo contactar la API" in response.content.decode()


class TestDerive:
    def test_success_clears_analysis_and_returns_home(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        client.get("/analisis/")
        response = client.post("/derivar/", _derive_form(), follow=True)
        assert "Carta #7 derivada al despacho." in response.content.decode()
        card = FakeApiClient.derived[0]
        assert card.answered_questions == [QUESTIONS[1]]
        assert card.pending_questions == [QUESTIONS[0]]
        assert client.get("/analisis/")["Location"] == "/"

    def test_missing_street_keeps_operator_edits(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        client.get("/analisis/")
        form = _derive_form(street="", priority="P2", street_number="1950", answered=QUESTIONS,
                            operator_notes="Llamante muy nervioso")
        response = client.post("/derivar/", form)
        html = response.content.decode()
        assert response.status_code == 422
        assert "La calle es obligatoria" in html
        assert "<option selected>P2</option>" in html
        assert 'value="1950"' in html and "Editado por el operador" in html
        assert "Llamante muy nervioso</textarea>" in html
        assert html.count("checked />") >= len(QUESTIONS)
        assert FakeApiClient.derived == []

    def test_api_error_keeps_operator_edits(self, client: Client) -> None:
        _analyze(client, transcript=TRANSCRIPT)
        client.get("/analisis/")
        FakeApiClient.fail_derive = True
        response = client.post("/derivar/", _derive_form(subcategory="Escape de gas"))
        assert response.status_code == 422
        assert "No se pudo derivar" in response.content.decode()
        assert 'value="Escape de gas"' in response.content.decode()

    def test_without_analysis_redirects_home(self, client: Client) -> None:
        assert client.post("/derivar/", _derive_form())["Location"] == "/"

    def test_confidence_is_not_localized_in_hidden_input(self, client: Client) -> None:
        # Regresión: es-ar renderizaba "0,9" y float() fallaba al derivar.
        _analyze(client, transcript=TRANSCRIPT)
        assert 'name="ai_confidence" value="0.9"' in client.get("/analisis/").content.decode()


def _stored_card() -> CallCardVM:
    return CallCardVM(
        id=3, created_at=datetime(2026, 11, 18, 10, 5), transcript=TRANSCRIPT, street="Thames", street_number="1900",
        intersection="Nicaragua y Costa Rica", neighborhood="Palermo", category="SERVICIOS_PUBLICOS",
        subcategory="Fuga de gas", priority="P1", answered_questions=[QUESTIONS[1]],
        pending_questions=[QUESTIONS[0]], instructions_given=["No accione interruptores."], risks=["Explosión"],
        suggested_resources="Bomberos", operator_notes="Llamante nervioso", ai_confidence=0.9, ai_provider="mock",
    )


class TestCardsPage:
    def test_lists_cards_with_full_detail(self, client: Client) -> None:
        FakeApiClient.stored_cards = [_stored_card()]
        html = client.get("/cartas/").content.decode()
        assert 'id="carta-3"' in html and '<span class="badge P1">P1</span>' in html
        assert "Thames 1900 (Nicaragua y Costa Rica)" in html and "Palermo" in html
        assert "1/2 respondidas" in html
        assert f"○ {QUESTIONS[0]}" in html and f"✓ {QUESTIONS[1]}" in html
        assert "No accione interruptores." in html and "Explosión" in html
        assert "Llamante nervioso" in html and "certeza 90%" in html
        assert "Ver transcripción" in html

    def test_empty_state(self, client: Client) -> None:
        assert "Todavía no se derivaron cartas." in client.get("/cartas/").content.decode()

    def test_api_error_is_shown(self, client: Client) -> None:
        FakeApiClient.fail_cards = True
        response = client.get("/cartas/")
        assert response.status_code == 200
        assert "No se pudieron cargar las cartas" in response.content.decode()

    def test_offers_going_back_to_the_current_analysis(self, client: Client) -> None:
        assert "Volver al análisis" not in client.get("/cartas/").content.decode()
        _analyze(client, transcript=TRANSCRIPT)
        client.get("/analisis/")
        assert "Volver al análisis" in client.get("/cartas/").content.decode()
