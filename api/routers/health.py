from django.http import HttpRequest
from ninja import Router

from services import container
from services.models import HealthStatus

router = Router()


@router.get("/health", response=HealthStatus)
def health(request: HttpRequest) -> HealthStatus:
    return HealthStatus(
        status="ok",
        provider=container.copilot_service().provider.name,
        catalog_size=len(container.catalog_service().cases()),
    )
