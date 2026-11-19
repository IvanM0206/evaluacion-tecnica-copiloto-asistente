"""`GET /api/health`."""

from __future__ import annotations

from pydantic import BaseModel


class HealthVM(BaseModel):
    status: str
    provider: str
    catalog_size: int
