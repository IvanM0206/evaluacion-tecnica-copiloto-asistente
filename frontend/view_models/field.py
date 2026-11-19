"""Un campo de ubicación extraído, con su evidencia literal y su estado de presentación."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class FieldVM(BaseModel):
    value: str | None
    evidence: str | None
    grounded: bool
    normalized: str | None = None

    @property
    def display_value(self) -> str:
        return self.normalized or self.value or ""

    @property
    def state(self) -> Literal["ok", "warn", "missing"]:
        if not self.value:
            return "missing"
        return "ok" if self.grounded else "warn"

    @property
    def hint(self) -> str:
        return {
            "missing": "No mencionado: preguntar",
            "warn": "⚠ Sin evidencia literal: verificar",
            "ok": f'✓ "{self.evidence or self.value}"',
        }[self.state]
