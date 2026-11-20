from __future__ import annotations

from typing import Any

from backend.choices import IncidentSource
from backend.models import CallCard as CallCardRow
from backend.models import Incident
from services.models import CallCard, Category, IncidentCreate, Priority, ReferenceCase


def incident_to_case(row: Incident) -> ReferenceCase:
    return ReferenceCase(
        id=row.external_id,
        source=row.source,
        origin=row.origin,
        category=Category(row.category),
        subcategory=row.subcategory,
        priority=Priority(row.priority),
        transcript=row.transcript,
        street=row.street,
        street_number=row.street_number,
        intersection=row.intersection,
        neighborhood=row.neighborhood,
        mandatory_questions=list(row.mandatory_questions),
        pending_questions=list(row.pending_questions),
        pre_arrival_instructions=row.pre_arrival_instructions,
        risks=list(row.risks),
        resources=row.resources,
        notes=row.notes,
    )


def incident_create_to_row(incident: IncidentCreate) -> dict[str, Any]:
    """Modelo de services -> fila del repositorio (mismas claves que produce `seed_dataset`)."""
    data = incident.model_dump()
    return {
        "external_id": data.pop("id"),
        "source": IncidentSource.SYNTHETIC,
        "called_at": None,
        **data,
    }


def call_card_row_to_model(row: CallCardRow) -> CallCard:
    return CallCard(
        id=row.pk,
        created_at=row.created_at,
        transcript=row.transcript,
        street=row.street,
        street_number=row.street_number or None,
        intersection=row.intersection or None,
        neighborhood=row.neighborhood or None,
        category=Category(row.category),
        subcategory=row.subcategory,
        priority=Priority(row.priority),
        answered_questions=list(row.answered_questions),
        pending_questions=list(row.pending_questions),
        ai_suggested_questions=list(row.ai_suggested_questions),
        instructions_given=list(row.instructions_given),
        risks=list(row.risks),
        suggested_resources=row.suggested_resources or None,
        operator_notes=row.operator_notes or None,
        ai_confidence=row.ai_confidence,
        ai_provider=row.ai_provider or None,
    )
