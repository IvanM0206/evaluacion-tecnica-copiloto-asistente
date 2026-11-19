"""ORM tables, one module per model. Only the backend layer touches these; services go through repositories.

Import from `backend.models` (this package re-exports every model).
"""

from __future__ import annotations

from backend.models.incident import Incident

__all__ = ["Incident"]
