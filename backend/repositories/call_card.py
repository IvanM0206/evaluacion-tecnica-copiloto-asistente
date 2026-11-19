"""Acceso a las Cartas de Llamada derivadas."""

from __future__ import annotations

from typing import Any

from backend.models import CallCard


class CallCardRepository:
    def create(self, **fields: Any) -> CallCard:
        return CallCard.objects.create(**fields)

    def list_recent(self, limit: int = 50) -> list[CallCard]:
        return list(CallCard.objects.all()[:limit])

    def get(self, card_id: int) -> CallCard | None:
        return CallCard.objects.filter(pk=card_id).first()
