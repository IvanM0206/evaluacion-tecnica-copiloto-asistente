"""Payload de salud de la API."""

from __future__ import annotations

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    provider: str
    catalog_size: int
