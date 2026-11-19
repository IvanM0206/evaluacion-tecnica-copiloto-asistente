"""Raíz de composición de la capa services.

Las capas superiores obtienen sus instancias de servicio desde acá (una por proceso),
así nunca construyen repositorios ni providers por su cuenta.
"""

from __future__ import annotations

from functools import lru_cache

from services.call_card_service import CallCardService
from services.catalog_service import CatalogService, DuplicateIncidentError
from services.copilot_service import CopilotService
from services.providers import ExtractionProvider, MockProvider

__all__ = [
    "DuplicateIncidentError",
    "build_provider",
    "call_card_service",
    "catalog_service",
    "copilot_service",
]


def build_provider() -> ExtractionProvider:
    # TODO: provider LLM real (elegido por LLM_PROVIDER + API key); mock hasta entonces.
    return MockProvider()


@lru_cache(maxsize=1)
def catalog_service() -> CatalogService:
    return CatalogService()


@lru_cache(maxsize=1)
def copilot_service() -> CopilotService:
    return CopilotService(catalog_service(), build_provider())


@lru_cache(maxsize=1)
def call_card_service() -> CallCardService:
    return CallCardService()
