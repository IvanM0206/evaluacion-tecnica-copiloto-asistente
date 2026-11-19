"""Acceso a datos, un módulo por agregado. El único punto de entrada de la capa services a la base de datos.

Los repositorios devuelven instancias del ORM; mapearlas a modelos de services es
tarea de la capa services (backend no debe importar capas superiores).
Importar desde `backend.repositories` (este paquete re-exporta todos los repositorios).
"""

from __future__ import annotations

from backend.repositories.incident import IncidentRepository

__all__ = ["IncidentRepository"]
