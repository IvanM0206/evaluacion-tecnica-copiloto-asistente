"""Modelos del front: lo que renderizan los templates y lo que envían los formularios.

Espejan el contrato JSON de la API pero son independientes de `services.models` a
propósito: el front solo conoce la API, nunca el código de services. Los helpers de
presentación (etiquetas, estados CSS, orden) viven acá, no en los templates.

Un módulo por modelo (o pequeña familia de modelos relacionados); todo se re-exporta
acá, así que siempre se importa desde `frontend.view_models`.
"""

from __future__ import annotations

from frontend.view_models.call_card import CallCardFormVM, CallCardVM
from frontend.view_models.checklist import ChecklistItemVM
from frontend.view_models.constants import CATEGORIES, PRIORITIES
from frontend.view_models.field import FieldVM
from frontend.view_models.health import HealthVM
from frontend.view_models.sample import SampleVM
from frontend.view_models.similar_case import SimilarCaseVM
from frontend.view_models.suggestion import SuggestionVM
from frontend.view_models.transcript_input import (
    MAX_UPLOAD_BYTES,
    MIN_TRANSCRIPT_CHARS,
    TranscriptInputError,
    decode_text_upload,
    transcript_from_submission,
)
from frontend.view_models.transcript_turns import TranscriptTurnVM, split_turns

__all__ = [
    "CATEGORIES",
    "MAX_UPLOAD_BYTES",
    "MIN_TRANSCRIPT_CHARS",
    "PRIORITIES",
    "CallCardFormVM",
    "CallCardVM",
    "ChecklistItemVM",
    "FieldVM",
    "HealthVM",
    "SampleVM",
    "SimilarCaseVM",
    "SuggestionVM",
    "TranscriptInputError",
    "TranscriptTurnVM",
    "decode_text_upload",
    "split_turns",
    "transcript_from_submission",
]
