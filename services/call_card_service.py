"""Derivación de Cartas de Llamada al despacho."""

from __future__ import annotations

from backend.repositories import CallCardRepository
from services.mappers import call_card_row_to_model
from services.models import CallCard, CallCardCreate

# Columnas de texto opcionales: en la DB se guardan como "" en lugar de NULL.
_OPTIONAL_TEXT = ("street_number", "intersection", "neighborhood", "suggested_resources", "operator_notes", "ai_provider")


class CallCardService:
    def __init__(self, repo: CallCardRepository | None = None) -> None:
        self._repo = repo or CallCardRepository()

    def derive(self, card: CallCardCreate) -> CallCard:
        # TODO: hand-off al sistema CAD (hoy la carta solo se persiste).
        data = card.model_dump()
        for key in _OPTIONAL_TEXT:
            data[key] = data[key] or ""
        row = self._repo.create(**data)
        return call_card_row_to_model(row)

    def recent(self, limit: int = 50) -> list[CallCard]:
        return [call_card_row_to_model(r) for r in self._repo.list_recent(limit)]
