from django.http import HttpRequest
from ninja import Router

from services import container
from services.models import AnalyzeRequest, CopilotSuggestion

router = Router()


@router.post("/analyze", response=CopilotSuggestion)
def analyze(request: HttpRequest, payload: AnalyzeRequest) -> CopilotSuggestion:
    return container.copilot_service().analyze(payload.transcript, simulate_llm=payload.simulate_llm)
