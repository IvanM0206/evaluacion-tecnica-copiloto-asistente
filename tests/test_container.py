"""Raíz de composición: selección del provider (dual provider) y una instancia por proceso."""

from __future__ import annotations

import pytest

from services import container
from services.providers import MockProvider


@pytest.mark.parametrize(
    ("requested", "key", "expected"),
    [
        ("mock", "sk-test", container.ProviderName.MOCK),
        ("", None, container.ProviderName.MOCK),
        ("anthropic", None, container.ProviderName.MOCK),
        ("anthropic", "sk-test", container.ProviderName.ANTHROPIC),
        ("", "sk-test", container.ProviderName.ANTHROPIC),
        ("ollama", "sk-test", container.ProviderName.MOCK),
    ],
)
def test_resolve_provider_name(
    monkeypatch: pytest.MonkeyPatch, settings, requested: str, key: str | None, expected: str  # type: ignore[no-untyped-def]
) -> None:
    settings.LLM_PROVIDER = requested
    if key:
        monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    assert container.resolve_provider_name() == expected


def test_test_run_uses_the_mock_provider() -> None:
    assert isinstance(container.build_provider(), MockProvider)


def test_anthropic_provider_is_built_with_the_configured_model(monkeypatch: pytest.MonkeyPatch, settings) -> None:  # type: ignore[no-untyped-def]
    from services.providers.anthropic_provider import AnthropicProvider

    settings.LLM_PROVIDER = "anthropic"
    settings.ANTHROPIC_MODEL = "claude-test"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    provider = container.build_provider()
    assert isinstance(provider, AnthropicProvider) and provider.model == "claude-test"


def test_services_are_process_singletons() -> None:
    assert container.catalog_service() is container.catalog_service()
    assert container.copilot_service() is container.copilot_service()


@pytest.mark.django_db
def test_copilot_service_uses_the_shared_catalog(seeded_db: None) -> None:
    copilot = container.copilot_service()
    assert copilot.provider.name == "mock"
    assert copilot.catalog is container.catalog_service().cases()
