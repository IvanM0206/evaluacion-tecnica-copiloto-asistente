"""Modelos de services: el contrato entre la capa services y la capa API.

Todo lo que cruza un límite (salida del LLM, payloads de la API, filas de la DB
mapeadas desde el backend) se valida acá. La capa API usa estas clases directamente
como esquemas de request/response.

Un módulo por familia; este paquete re-exporta todo, así que siempre se importa
desde `services.models`.
"""

from __future__ import annotations

from backend.choices import Category, Priority
from services.models.catalog import IncidentCreate, ReferenceCase, SampleTranscript
from services.models.extraction import ChecklistAnswer, ExtractedField, RawExtraction
from services.models.health import HealthStatus
from services.models.suggestion import (
    AnalyzeRequest,
    ChecklistItem,
    CopilotSuggestion,
    GroundedField,
    SimilarCase,
)

__all__ = [
    "AnalyzeRequest",
    "Category",
    "ChecklistAnswer",
    "ChecklistItem",
    "CopilotSuggestion",
    "ExtractedField",
    "GroundedField",
    "HealthStatus",
    "IncidentCreate",
    "Priority",
    "RawExtraction",
    "ReferenceCase",
    "SampleTranscript",
    "SimilarCase",
]
