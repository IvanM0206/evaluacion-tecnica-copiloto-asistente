"""Data access, one module per aggregate. The only entry point from the services layer into the database.

Repositories return ORM instances; mapping them to service models is the
services layer's job (backend must not import upper layers).
Import from `backend.repositories` (this package re-exports every repository).
"""

from __future__ import annotations

from backend.repositories.incident import IncidentRepository

__all__ = ["IncidentRepository"]
