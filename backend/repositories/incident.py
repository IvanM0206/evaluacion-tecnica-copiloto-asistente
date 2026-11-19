from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.choices import IncidentSource
from backend.models import Incident


class IncidentRepository:
    def list_all(self, source: IncidentSource | None = None) -> list[Incident]:
        qs = Incident.objects.all()
        if source is not None:
            qs = qs.filter(source=source)
        return list(qs)

    def get_by_external_id(self, external_id: str) -> Incident | None:
        return Incident.objects.filter(external_id=external_id).first()

    def upsert_many(self, rows: Iterable[dict[str, Any]]) -> int:
        """Idempotent load keyed by `external_id`. Returns how many rows were written."""
        count = 0
        for row in rows:
            data = dict(row)
            external_id = data.pop("external_id")
            Incident.objects.update_or_create(external_id=external_id, defaults=data)
            count += 1
        return count

    def count(self) -> int:
        return Incident.objects.count()
