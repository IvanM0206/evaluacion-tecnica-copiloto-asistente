"""Capa 4 · Vistas del front. HTML renderizado en el servidor; los datos llegan solo por el cliente de la API.

Flujo (sin JavaScript):

    GET  /             pantalla inicial: card centrada para escribir, subir o usar una transcripción de ejemplo
    POST /analizar/    valida la entrada, la guarda como *pendiente* en la sesión y redirige a /cargando/
    GET  /cargando/    loader a pantalla completa; un meta refresh navega a /analisis/ y el navegador
                       sigue mostrando el loader mientras corre ese request
    GET  /analisis/    analiza la transcripción pendiente (si hay) a través de la API y renderiza el
                       workspace: transcripción a la izquierda, sugerencia a la derecha. El análisis
                       actual solo se reemplaza cuando el nuevo sale bien.
"""

from __future__ import annotations

from typing import Any, Literal

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from frontend.client import ApiClient, ApiError
from frontend.view_models import (
    SuggestionVM,
    TranscriptInputError,
    split_turns,
    transcript_from_submission,
)

# Ejemplo ofrecido como "plantilla de ejemplo": una fuga de gas P1 con calle, altura y esquinas.
DEMO_SAMPLE_ID = "SFX-REC-2026-012"

_ANALYSIS_KEY = "copilot_analysis"  # análisis actual: {"transcript": str, "suggestion": dict}
_PENDING_KEY = "copilot_pending"  # transcripción enviada y todavía sin analizar
_DRAFT_KEY = "copilot_draft"  # texto a devolverle al operador tras una entrada rechazada o fallida

LeftMode = Literal["view", "edit", "new"]


def _base_context(request: HttpRequest, client: ApiClient) -> dict[str, Any]:
    context: dict[str, Any] = {"health": None, "demo_sample_id": DEMO_SAMPLE_ID}
    try:
        context["health"] = client.health()
    except ApiError as exc:
        messages.error(request, str(exc))
    return context


def _sample_transcript(request: HttpRequest, client: ApiClient, sample_id: str) -> str:
    try:
        return client.sample(sample_id).transcript
    except ApiError as exc:
        messages.error(request, f"No se pudo cargar la plantilla: {exc}")
        return ""


@require_GET
def index(request: HttpRequest) -> HttpResponse:
    client = ApiClient()
    context = _base_context(request, client)
    transcript = request.session.pop(_DRAFT_KEY, "")
    if sample_id := request.GET.get("sample"):
        transcript = _sample_transcript(request, client, sample_id)
    context.update(transcript=transcript, has_analysis=_ANALYSIS_KEY in request.session)
    return render(request, "frontend/index.html", context)


@require_POST
def analyze(request: HttpRequest) -> HttpResponse:
    try:
        transcript = transcript_from_submission(request.POST, request.FILES)
    except TranscriptInputError as exc:
        messages.warning(request, str(exc))
        request.session[_DRAFT_KEY] = (request.POST.get("transcript") or "").strip()
        return _back_to_input(request)
    request.session[_PENDING_KEY] = transcript
    return redirect("frontend:loading")


def _back_to_input(request: HttpRequest) -> HttpResponse:
    """Dónde reintentar: el panel "Nueva transcripción" del workspace, o la pantalla inicial."""
    if _ANALYSIS_KEY in request.session:
        return redirect("frontend:workspace")
    return redirect("frontend:index")


@require_GET
def loading(request: HttpRequest) -> HttpResponse:
    if _PENDING_KEY not in request.session and _ANALYSIS_KEY not in request.session:
        return redirect("frontend:index")
    return render(request, "frontend/loading.html")


@require_GET
def workspace(request: HttpRequest) -> HttpResponse:
    client = ApiClient()
    if pending := request.session.pop(_PENDING_KEY, None):
        try:
            suggestion = client.analyze(pending)
        except ApiError as exc:
            # Conserva el análisis anterior (si hay) y devuelve el texto para reintentar.
            messages.error(request, f"Error al analizar: {exc}")
            request.session[_DRAFT_KEY] = pending
            return _back_to_input(request)
        request.session[_ANALYSIS_KEY] = {
            "transcript": pending,
            "suggestion": suggestion.model_dump(mode="json"),
        }

    state: dict[str, Any] | None = request.session.get(_ANALYSIS_KEY)
    if not state:
        return redirect("frontend:index")
    suggestion = SuggestionVM.model_validate(state["suggestion"])

    mode: LeftMode = "view"
    new_transcript = ""
    if draft := request.session.pop(_DRAFT_KEY, ""):
        mode, new_transcript = "new", draft
    elif sample_id := request.GET.get("sample"):
        mode = "new"
        new_transcript = _sample_transcript(request, client, sample_id)
    elif request.GET.get("modo") in ("edit", "new"):
        mode = request.GET["modo"]  # type: ignore[assignment]

    context = _base_context(request, client)
    context.update(
        transcript=state["transcript"],
        turns=split_turns(state["transcript"]),
        suggestion=suggestion,
        mode=mode,
        new_transcript=new_transcript,
    )
    return render(request, "frontend/workspace.html", context)
