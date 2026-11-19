"""CatalogService: casos de referencia desde la DB, incidentes sintéticos y ejemplos de demo."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from backend.choices import IncidentSource
from services.catalog_service import CatalogService, DuplicateIncidentError
from services.models import Category, IncidentCreate, Priority

pytestmark = pytest.mark.django_db

FIRE_ID = "SFX-REC-2026-001"

SYNTHETIC = IncidentCreate(
    id="SYN-0001",
    category=Category.DEFENSA_CIVIL,
    subcategory="Caída de árbol sobre vehículo",
    priority=Priority.P2,
    transcript="Operador: 911. Llamante: Se cayó un árbol arriba de un auto en Thames 1900.",
    street="Thames",
    street_number="1900",
    mandatory_questions=["¿Hay personas dentro del vehículo?"],
)


def test_cases_are_mapped_from_the_db(seeded_db: None) -> None:
    cases = CatalogService().cases()
    assert len(cases) == 30
    fire = next(c for c in cases if c.id == FIRE_ID)
    assert fire.category == Category.INCENDIO_RESCATE
    assert fire.source == IncidentSource.DATASET
    assert fire.mandatory_questions and isinstance(fire.mandatory_questions, list)


def test_add_stores_a_synthetic_incident_and_notifies_listeners(seeded_db: None) -> None:
    catalog = CatalogService()
    catalog.cases()
    notified: list[bool] = []
    catalog.on_change(lambda: notified.append(True))

    case = catalog.add(SYNTHETIC)

    assert case.id == "SYN-0001" and case.source == IncidentSource.SYNTHETIC
    assert len(catalog.cases()) == 31
    assert notified == [True]


def test_add_rejects_an_existing_id(seeded_db: None) -> None:
    with pytest.raises(DuplicateIncidentError):
        CatalogService().add(SYNTHETIC.model_copy(update={"id": FIRE_ID}))


def test_cache_is_refreshed_when_rows_are_added_elsewhere(db: None) -> None:
    catalog = CatalogService()
    assert catalog.cases() == []
    call_command("seed_dataset", verbosity=0)  # p. ej. otro worker de gunicorn o una carga por CLI
    assert len(catalog.cases()) == 30


def test_samples_expose_dataset_transcripts(seeded_db: None) -> None:
    catalog = CatalogService()
    sample = catalog.get_sample(FIRE_ID)
    assert sample is not None and sample.label.startswith(f"{FIRE_ID} · ")
    assert sample.transcript.startswith("Operador:")
    assert catalog.get_sample("NO-EXISTE") is None
    assert len(catalog.samples()) == 30
