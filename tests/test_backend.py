from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

from backend.choices import IncidentSource
from backend.management.commands.seed_dataset import csv_to_rows
from backend.repositories import IncidentRepository


def test_csv_to_rows_parses_lists_and_timestamps() -> None:
    rows = csv_to_rows(settings.DATASET_PATH, IncidentSource.DATASET)
    assert len(rows) == 30
    first = rows[0]
    assert first["external_id"] == "SFX-REC-2026-001"
    assert first["called_at"] is not None and first["called_at"].tzinfo is not None
    assert isinstance(first["mandatory_questions"], list) and first["mandatory_questions"]
    assert isinstance(first["risks"], list)


@pytest.mark.django_db
def test_seed_dataset_loads_the_whole_csv(seeded_db: None) -> None:
    repo = IncidentRepository()
    assert repo.count() == 30
    categories = Counter(i.category for i in repo.list_all())
    assert categories["INCENDIO_RESCATE"] == 8
    assert categories["EMERGENCIA_MEDICA"] == 6


@pytest.mark.django_db
def test_seed_dataset_is_idempotent(seeded_db: None) -> None:
    call_command("seed_dataset", verbosity=0)
    assert IncidentRepository().count() == 30


@pytest.mark.django_db
def test_seed_dataset_with_synthetic_source(tmp_path: Path) -> None:
    lines = Path(settings.DATASET_PATH).read_text(encoding="utf-8").splitlines(keepends=True)
    one_row = tmp_path / "synthetic.csv"
    one_row.write_text(lines[0] + lines[1].replace("SFX-REC-2026-001", "SYN-0001", 1), encoding="utf-8")

    call_command("seed_dataset", str(one_row), "--source", "SYNTHETIC", verbosity=0)

    repo = IncidentRepository()
    assert [i.external_id for i in repo.list_all(IncidentSource.SYNTHETIC)] == ["SYN-0001"]
    assert repo.list_all(IncidentSource.DATASET) == []
    assert repo.get_by_external_id("SYN-0001") is not None
    assert repo.get_by_external_id("NO-EXISTE") is None
