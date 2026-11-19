from django.http import HttpRequest
from ninja import Router

from services import container
from services.models import CallCard, CallCardCreate

router = Router()


@router.post("", response={201: CallCard})
def derive_card(request: HttpRequest, payload: CallCardCreate) -> tuple[int, CallCard]:
    return 201, container.call_card_service().derive(payload)


@router.get("", response=list[CallCard])
def list_cards(request: HttpRequest, limit: int = 50) -> list[CallCard]:
    return container.call_card_service().recent(limit)
