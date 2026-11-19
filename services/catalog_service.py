"""Catálogo de referencia: incidentes guardados en la DB, como modelos tipados de services."""

from __future__ import annotations

from collections.abc import Callable

from backend.repositories import IncidentRepository
from services.mappers import incident_create_to_row, incident_to_case
from services.models import IncidentCreate, ReferenceCase, SampleTranscript


class DuplicateIncidentError(ValueError):
    """Ya existe en el catálogo un incidente con ese id."""


class CatalogService:
    def __init__(self, repo: IncidentRepository | None = None) -> None:
        self._repo = repo or IncidentRepository()
        self._cache: list[ReferenceCase] | None = None
        self._listeners: list[Callable[[], None]] = []

    def cases(self) -> list[ReferenceCase]:
        # Cacheado por proceso. Un COUNT barato detecta incidentes agregados por otro worker
        # (gunicorn corre varios) o por `seed_dataset` en caliente; las ediciones de filas
        # existentes (p. ej. desde el admin) todavía requieren reiniciar.
        if self._cache is not None and len(self._cache) != self._repo.count():
            self.refresh()
        if self._cache is None:
            self._cache = [incident_to_case(row) for row in self._repo.list_all()]
        return self._cache

    def on_change(self, listener: Callable[[], None]) -> None:
        """Registra un callback que se ejecuta cuando cambia el catálogo (p. ej. para reconstruir índices)."""
        self._listeners.append(listener)

    def refresh(self) -> None:
        self._cache = None
        for listener in self._listeners:
            listener()

    def add(self, incident: IncidentCreate) -> ReferenceCase:
        """Agrega un incidente sintético; se usa para el retrieval desde el próximo análisis."""
        if self._repo.get_by_external_id(incident.id) is not None:
            raise DuplicateIncidentError(f"Ya existe un incidente con id {incident.id}")
        self._repo.upsert_many([incident_create_to_row(incident)])
        self.refresh()
        row = self._repo.get_by_external_id(incident.id)
        assert row is not None
        return incident_to_case(row)

    def samples(self) -> list[SampleTranscript]:
        """Transcripciones del dataset para mostrar el flujo sin tipear."""
        return [
            SampleTranscript(id=c.id, label=f"{c.id} · {c.subcategory}", transcript=c.transcript)
            for c in self.cases()
        ]

    def get_sample(self, sample_id: str) -> SampleTranscript | None:
        return next((s for s in self.samples() if s.id == sample_id), None)
