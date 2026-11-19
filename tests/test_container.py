"""Raíz de composición: una instancia por proceso, cableada con el provider mock determinista."""

from __future__ import annotations

import pytest

from services import container
from services.providers import MockProvider


def test_provider_is_the_deterministic_mock() -> None:
    assert isinstance(container.build_provider(), MockProvider)


def test_services_are_process_singletons() -> None:
    assert container.catalog_service() is container.catalog_service()
    assert container.copilot_service() is container.copilot_service()


@pytest.mark.django_db
def test_copilot_service_uses_the_shared_catalog(seeded_db: None) -> None:
    copilot = container.copilot_service()
    assert copilot.provider.name == "mock"
    assert copilot.catalog is container.catalog_service().cases()
