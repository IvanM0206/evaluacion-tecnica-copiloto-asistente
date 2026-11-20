"""`GET /api/health`."""

from __future__ import annotations

from pydantic import BaseModel


class HealthVM(BaseModel):
    status: str
    provider: str
    catalog_size: int

    @property
    def llm_active(self) -> bool:
        """Responde un LLM real; si no, el panel ofrece simularlo."""
        return not self.provider.startswith("mock")
