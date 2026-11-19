"""Fixtures compartidas. La suite es offline y determinista: solo provider mock, sin red."""

from __future__ import annotations

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
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hace que cualquier conexión de red real falle de forma explícita."""

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
