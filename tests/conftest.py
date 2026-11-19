from __future__ import annotations

import pytest
from django.core.management import call_command


@pytest.fixture
def seeded_db(db: None) -> None:
    """Load the challenge CSV into the test database."""
    call_command("seed_dataset", verbosity=0)
