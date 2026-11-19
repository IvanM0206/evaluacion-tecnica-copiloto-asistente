"""Un campo de ubicación extraído, con su evidencia literal y su estado de presentación."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class FieldVM(BaseModel):
    value: str | None
    evidence: str | None
    grounded: bool
    normalized: str | None = None
    edited: bool = False  # el operador cambió el valor sugerido

    @property
    def display_value(self) -> str:
        return self.normalized or self.value or ""

    @property
    def state(self) -> Literal["ok", "warn", "missing", "edited"]:
        if not self.value:
            return "missing"
        if self.edited:
            return "edited"
        return "ok" if self.grounded else "warn"

    @property
    def hint(self) -> str:
        return {
            "missing": "No mencionado: preguntar",
            "warn": "⚠ Sin evidencia literal: verificar",
            "edited": "✎ Editado por el operador",
            "ok": f'✓ "{self.evidence or self.value}"',
        }[self.state]

    def with_value(self, value: str | None) -> FieldVM:
        """Este campo después de la edición del operador (si no cambió, conserva su evidencia)."""
        value = (value or "").strip() or None
        if value == (self.display_value or None):
            return self
        return FieldVM(value=value, evidence=None, grounded=False, edited=value is not None)
