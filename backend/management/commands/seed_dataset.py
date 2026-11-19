"""Carga el CSV del challenge (o cualquier CSV con las mismas columnas) en la tabla Incident.

    python manage.py seed_dataset                      # dataset provisto
    python manage.py seed_dataset otro.csv --source SYNTHETIC
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from backend.choices import IncidentSource
from backend.repositories import IncidentRepository


def _split(value: str, sep: str = "|") -> list[str]:
    return [part.strip() for part in (value or "").split(sep) if part.strip()]


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


def csv_to_rows(path: Path, source: IncidentSource) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("id_registro"):
                continue  # líneas vacías al final
            rows.append(
                {
                    "external_id": r["id_registro"],
                    "source": source,
                    "called_at": _parse_ts(r["timestamp_llamada"]),
                    "origin": r["origen_reporte"],
                    "category": r["categoria"],
                    "subcategory": r["subcategoria"],
                    "priority": r["prioridad_sugerida"],
                    "transcript": r["transcripcion_cruda"],
                    "street": r["calle_detectada"],
                    "street_number": r["altura_detectada"],
                    "intersection": r["interseccion_detectada"],
                    "neighborhood": r["barrio_comuna"],
                    "mandatory_questions": _split(r["preguntas_protocolo_mandatorias"]),
                    "answered_questions": _split(r["preguntas_respondidas_en_relato"]),
                    "pending_questions": _split(r["preguntas_pendientes"]),
                    "pre_arrival_instructions": r["instrucciones_prearribo"],
                    "risks": _split(r["riesgos_detectados"], ","),
                    "resources": r["recursos_recomendados_despacho"],
                    "notes": r["notas_operativas_despacho"],
                }
            )
    return rows


class Command(BaseCommand):
    help = "Carga incidentes desde un CSV con el formato del dataset del challenge (idempotente)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("path", nargs="?", default=str(settings.DATASET_PATH))
        parser.add_argument("--source", choices=IncidentSource.values, default=IncidentSource.DATASET)

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["path"])
        written = IncidentRepository().upsert_many(csv_to_rows(path, IncidentSource(options["source"])))
        self.stdout.write(self.style.SUCCESS(f"{written} incidentes cargados desde {path}"))
