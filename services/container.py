"""Raíz de composición de la capa services.

Las capas superiores obtienen sus instancias de servicio desde acá (una por proceso),
así nunca construyen repositorios ni providers por su cuenta.
"""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache

from django.conf import settings

from services.call_card_service import CallCardService
from services.catalog_service import CatalogService, DuplicateIncidentError
from services.copilot_service import CopilotService
from services.providers import ExtractionProvider, MockProvider

__all__ = [
    "DuplicateIncidentError",
    "ProviderName",
    "build_provider",
    "call_card_service",
    "catalog_service",
    "copilot_service",
    "resolve_provider_name",
]


class ProviderName(StrEnum):
    MOCK = "mock"
    ANTHROPIC = "anthropic"


def resolve_provider_name() -> ProviderName:
    """LLM real solo si se pide (o no se define) y hay una key; si no, mock."""
    requested = settings.LLM_PROVIDER
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    if requested in ("", ProviderName.ANTHROPIC) and has_key:
        return ProviderName.ANTHROPIC
    # TODO: sumar acá providers de OpenAI / Gemini / Ollama (cada uno implementa ExtractionProvider).
    return ProviderName.MOCK


def build_provider() -> ExtractionProvider:
    if resolve_provider_name() == ProviderName.ANTHROPIC:
        from services.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=settings.ANTHROPIC_MODEL)
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
