"""Tablas del ORM, un módulo por modelo. Solo la capa backend las toca; services pasa por los repositorios.

Importar desde `backend.models` (este paquete re-exporta todos los modelos).
"""

from __future__ import annotations

from backend.models.incident import Incident

__all__ = ["Incident"]
