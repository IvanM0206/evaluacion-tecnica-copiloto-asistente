"""Endpoints HTTP (Django Ninja) a través del test client de Django, con el dataset cargado."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

FIRE_ID = "SFX-REC-2026-001"


@pytest.fixture
def api(seeded_db: None) -> Client:
    return Client()


def test_health_reports_mock_provider_and_catalog_size(api: Client) -> None:
    response = api.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "provider": "mock", "catalog_size": 30}


def test_samples_list(api: Client) -> None:
    response = api.get("/api/catalog/samples")
    assert response.status_code == 200
    samples = response.json()
    assert len(samples) == 30
    assert {"id", "label", "transcript"} <= samples[0].keys()


def test_sample_detail(api: Client) -> None:
    response = api.get(f"/api/catalog/samples/{FIRE_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == FIRE_ID
    assert "Av. Corrientes 1540" in body["transcript"]


def test_unknown_sample_is_404(api: Client) -> None:
    response = api.get("/api/catalog/samples/NO-EXISTE")
    assert response.status_code == 404
    assert response.json()["detail"] == "Transcripción NO-EXISTE no encontrada"


def test_incidents_list(api: Client) -> None:
    response = api.get("/api/catalog/incidents")
    assert response.status_code == 200
    incidents = response.json()
    assert len(incidents) == 30
    assert {"id", "category", "priority", "street", "mandatory_questions"} <= incidents[0].keys()


def test_analyze_returns_grounded_suggestion(api: Client) -> None:
    transcript = api.get(f"/api/catalog/samples/{FIRE_ID}").json()["transcript"]
    response = api.post("/api/copilot/analyze", {"transcript": transcript}, content_type="application/json")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["category"] == "INCENDIO_RESCATE"
    assert body["priority"] == "P1"
    assert body["street"]["grounded"] is True
    assert body["street"]["normalized"] == "Av. Corrientes"
    assert body["checklist"] and body["pre_arrival_instructions"]
    assert FIRE_ID not in {c["id"] for c in body["similar_cases"]}


@pytest.mark.parametrize("payload", [{"transcript": "corto"}, {}, {"transcript": "x" * 20_001}])
def test_analyze_rejects_invalid_requests(api: Client, payload: dict[str, str]) -> None:
    response = api.post("/api/copilot/analyze", payload, content_type="application/json")
    assert response.status_code == 422


SYNTHETIC_INCIDENT = {
    "id": "SYN-TEST-001",
    "category": "DEFENSA_CIVIL",
    "subcategory": "Caída de cornisa",
    "priority": "P2",
    "transcript": "Operador: 103. Llamante: Se cayó un pedazo de cornisa en Thames 1900.",
    "mandatory_questions": ["¿Hay personas lesionadas?"],
}


def test_create_synthetic_incident_then_duplicate_is_409(api: Client, settings) -> None:  # type: ignore[no-untyped-def]
    settings.CATALOG_API_TOKEN = "s3cret"
    headers = {"HTTP_X_CATALOG_TOKEN": "s3cret"}
    created = api.post("/api/catalog/incidents", SYNTHETIC_INCIDENT, content_type="application/json", **headers)
    assert created.status_code == 201
    assert created.json()["id"] == "SYN-TEST-001"
    assert created.json()["source"] == "SYNTHETIC"
    assert api.get("/api/health").json()["catalog_size"] == 31

    duplicate = api.post("/api/catalog/incidents", SYNTHETIC_INCIDENT, content_type="application/json", **headers)
    assert duplicate.status_code == 409


@pytest.mark.parametrize(
    ("configured", "sent"),
    [("", None), ("", ""), ("s3cret", None), ("s3cret", "wrong")],
    ids=["disabled", "disabled-empty-header", "missing-header", "wrong-token"],
)
def test_create_incident_requires_token(api: Client, settings, configured: str, sent: str | None) -> None:  # type: ignore[no-untyped-def]
    # Las escrituras al catálogo alimentan el protocolo que se lee a llamantes reales: nunca abiertas por defecto.
    settings.CATALOG_API_TOKEN = configured
    headers = {} if sent is None else {"HTTP_X_CATALOG_TOKEN": sent}
    response = api.post("/api/catalog/incidents", SYNTHETIC_INCIDENT, content_type="application/json", **headers)
    assert response.status_code == 401
    assert api.get("/api/health").json()["catalog_size"] == 30


def test_openapi_docs_are_served(api: Client) -> None:
    assert api.get("/api/docs").status_code == 200
    paths = api.get("/api/openapi.json").json()["paths"]
    assert {"/api/health", "/api/catalog/samples", "/api/copilot/analyze", "/api/cards"} <= paths.keys()


# ------------------------------------------------------------------ cartas
def _card_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "transcript": "Operador: 911. Llamante: Se prendió fuego la cocina en Av. Corrientes 1540.",
        "street": "Av. Corrientes",
        "street_number": "1540",
        "intersection": "Montevideo",
        "category": "INCENDIO_RESCATE",
        "subcategory": "Incendio en Comercio Gastronómico",
        "priority": "P1",
        "answered_questions": ["¿Hay personas atrapadas en el interior?"],
        "pending_questions": ["¿Pudo cortar la llave de gas general?"],
        "instructions_given": ["No reingresar al local por ningún motivo."],
        "risks": ["Personas atrapadas"],
        "ai_confidence": 0.82,
        "ai_provider": "mock",
    }
    payload.update(overrides)
    return payload


def test_create_card_returns_201_and_is_listed(api: Client) -> None:
    created = api.post("/api/cards", _card_payload(), content_type="application/json")
    assert created.status_code == 201
    card = created.json()
    assert card["id"] > 0 and card["created_at"]
    assert card["street"] == "Av. Corrientes" and card["street_number"] == "1540"
    assert card["neighborhood"] is None, "el texto opcional vacío vuelve como null"

    listed = api.get("/api/cards")
    assert listed.status_code == 200
    assert [c["id"] for c in listed.json()] == [card["id"]]


def test_cards_are_listed_newest_first_and_respect_limit(api: Client) -> None:
    ids = [
        api.post("/api/cards", _card_payload(street_number=n), content_type="application/json").json()["id"]
        for n in ("100", "200", "300")
    ]
    assert [c["id"] for c in api.get("/api/cards?limit=2").json()] == ids[::-1][:2]


@pytest.mark.parametrize("override", [{"street": ""}, {"priority": "P9"}, {"category": "OVNI"}])
def test_create_card_rejects_invalid_payload(api: Client, override: dict[str, str]) -> None:
    response = api.post("/api/cards", _card_payload(**override), content_type="application/json")
    assert response.status_code == 422


def test_cards_empty_list(api: Client) -> None:
    assert api.get("/api/cards").json() == []
