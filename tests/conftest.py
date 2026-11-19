"""Fixtures compartidas. La suite es offline y determinista: solo provider mock, sin red."""

from __future__ import annotations

import os

# Tiene que pasar antes de importar los settings de Django (LLM_PROVIDER se lee al importar).
os.environ["LLM_PROVIDER"] = "mock"
os.environ.pop("ANTHROPIC_API_KEY", None)

import socket
from collections.abc import Callable, Iterator

import pytest
from django.conf import settings as django_settings
from django.core.management import call_command

from backend.choices import IncidentSource
from backend.management.commands.seed_dataset import csv_to_rows
from services import container
from services.models import ReferenceCase


@pytest.fixture(autouse=True)
def _offline_mock_provider(monkeypatch: pytest.MonkeyPatch, settings) -> None:  # type: ignore[no-untyped-def]
    """Fuerza el provider mock y hace que cualquier conexión de red real falle de forma explícita."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings.LLM_PROVIDER = "mock"

    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Network access is disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)


@pytest.fixture(autouse=True)
def _reset_service_singletons() -> Iterator[None]:
    """Los servicios cachean instancias (y sus índices lazy / caché del catálogo) por proceso."""
    for factory in (container.catalog_service, container.copilot_service, container.call_card_service):
        factory.cache_clear()
    yield
    for factory in (container.catalog_service, container.copilot_service, container.call_card_service):
        factory.cache_clear()


@pytest.fixture(scope="session")
def reference_cases() -> list[ReferenceCase]:
    """Las 30 filas del dataset como modelos de services, parseadas directo del CSV (sin DB)."""
    rows = csv_to_rows(django_settings.DATASET_PATH, IncidentSource.DATASET)
    return [
        ReferenceCase(
            id=row["external_id"],
            **{k: v for k, v in row.items() if k in ReferenceCase.model_fields and k != "id"},
        )
        for row in rows
    ]


@pytest.fixture
def case_by_id(reference_cases: list[ReferenceCase]) -> dict[str, ReferenceCase]:
    return {c.id: c for c in reference_cases}


class FakeCatalog:
    """Reemplaza a CatalogService (CopilotService usa `cases()` y `on_change()`)."""

    def __init__(self, cases: list[ReferenceCase]) -> None:
        self._cases = cases
        self.listeners: list[Callable[[], None]] = []

    def cases(self) -> list[ReferenceCase]:
        return self._cases

    def on_change(self, listener: Callable[[], None]) -> None:
        self.listeners.append(listener)


@pytest.fixture
def fake_catalog(reference_cases: list[ReferenceCase]) -> FakeCatalog:
    return FakeCatalog(reference_cases)


@pytest.fixture
def seeded_db(db: None) -> None:
    """Carga el CSV del challenge en la base de datos de test."""
    call_command("seed_dataset", verbosity=0)
