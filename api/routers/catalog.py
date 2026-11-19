import hmac

from django.conf import settings
from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError
from ninja.security import APIKeyHeader

from services import container
from services.models import IncidentCreate, ReferenceCase, SampleTranscript

router = Router()


class CatalogToken(APIKeyHeader):
    """`X-Catalog-Token` tiene que coincidir con settings.CATALOG_API_TOKEN (sin definir = escrituras deshabilitadas).

    Al ser un header propio (no una cookie) también descarta posts cross-site desde formularios (sin CSRF).
    """

    param_name = "X-Catalog-Token"

    def authenticate(self, request: HttpRequest, key: str | None) -> str | None:
        expected = settings.CATALOG_API_TOKEN
        if expected and key and hmac.compare_digest(key, expected):
            return key
        return None


@router.get("/samples", response=list[SampleTranscript])
def list_samples(request: HttpRequest) -> list[SampleTranscript]:
    """Transcripciones del dataset para mostrar el flujo sin tipear."""
    return container.catalog_service().samples()


@router.get("/samples/{sample_id}", response=SampleTranscript)
def get_sample(request: HttpRequest, sample_id: str) -> SampleTranscript:
    sample = container.catalog_service().get_sample(sample_id)
    if sample is None:
        raise HttpError(404, f"Transcripción {sample_id} no encontrada")
    return sample


@router.get("/incidents", response=list[ReferenceCase])
def list_incidents(request: HttpRequest) -> list[ReferenceCase]:
    """Catálogo de referencia completo (dataset + incidentes sintéticos)."""
    return container.catalog_service().cases()


@router.post("/incidents", response={201: ReferenceCase}, auth=CatalogToken())
def create_incident(request: HttpRequest, payload: IncidentCreate) -> tuple[int, ReferenceCase]:
    """Agrega un incidente sintético/hipotético al catálogo de referencia en caliente.

    Se guarda con source SYNTHETIC y se usa en el retrieval (preguntas de protocolo,
    instrucciones pre-arribo) desde el próximo análisis, sin reiniciar.
    """
    try:
        return 201, container.catalog_service().add(payload)
    except container.DuplicateIncidentError as exc:
        raise HttpError(409, str(exc)) from exc
