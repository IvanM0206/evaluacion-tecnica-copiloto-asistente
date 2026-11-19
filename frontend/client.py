"""Cliente HTTP de la capa API. La única forma que tiene el front de obtener o enviar datos.

Las respuestas se parsean a view models del front; cualquier problema de transporte,
HTTP o validación se expone como `ApiError` para que las vistas se lo muestren al operador.
"""

from __future__ import annotations

from typing import Any, TypeVar
from urllib.parse import quote

import httpx
from django.conf import settings
from pydantic import TypeAdapter, ValidationError

from frontend.view_models import CallCardFormVM, CallCardVM, HealthVM, SampleVM, SuggestionVM

T = TypeVar("T")


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self._base_url = (base_url or settings.API_BASE_URL).rstrip("/")
        self._timeout = timeout or settings.API_TIMEOUT_SECONDS

    # ---------------------------------------------------------------- llamadas
    def health(self) -> HealthVM:
        return self._get("/health", HealthVM)

    def samples(self) -> list[SampleVM]:
        return self._get("/catalog/samples", list[SampleVM])

    def sample(self, sample_id: str) -> SampleVM:
        return self._get(f"/catalog/samples/{quote(sample_id, safe='')}", SampleVM)

    def analyze(self, transcript: str) -> SuggestionVM:
        return self._send("POST", "/copilot/analyze", {"transcript": transcript}, SuggestionVM)

    def derive_card(self, card: CallCardFormVM) -> CallCardVM:
        return self._send("POST", "/cards", card.model_dump(), CallCardVM)

    def cards(self) -> list[CallCardVM]:
        return self._get("/cards", list[CallCardVM])

    # -------------------------------------------------------------- auxiliares
    def _get(self, path: str, model: type[T]) -> T:
        return self._send("GET", path, None, model)

    def _send(self, method: str, path: str, body: dict[str, Any] | None, model: type[T]) -> T:
        try:
            with httpx.Client(base_url=self._base_url, timeout=self._timeout) as http:
                res = http.request(method, path, json=body)
        except httpx.HTTPError as exc:
            raise ApiError(f"No se pudo contactar la API ({exc.__class__.__name__})") from exc
        if res.is_error:
            raise ApiError(f"La API respondió {res.status_code}: {res.text[:300]}")
        try:
            return TypeAdapter(model).validate_python(res.json())
        except (ValidationError, ValueError) as exc:
            raise ApiError("Respuesta de la API con formato inesperado") from exc
