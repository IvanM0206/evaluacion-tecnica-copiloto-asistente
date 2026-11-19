"""`GET /api/catalog/samples[/{id}]`: transcripciones de ejemplo."""

from __future__ import annotations

from pydantic import BaseModel


class SampleVM(BaseModel):
    id: str
    label: str
    transcript: str
