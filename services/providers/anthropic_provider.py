"""Provider respaldado por Claude (LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY).

Usa structured outputs (`output_format=<modelo pydantic>`), así el SDK valida la respuesta
contra el esquema; cualquier otra cosa lanza ProviderError y el orquestador cae al mock.
Los textos del prompt viven en `services.prompts`.
"""

from __future__ import annotations

import anthropic
import pydantic

from services.models import RawExtraction
from services.prompts import EXTRACTION_PROMPT, build_extraction_user_message
from services.providers.base import ExtractionContext, ProviderError

MAX_TOKENS = 16_000
EFFORT = "low"
REQUEST_TIMEOUT_SECONDS = 20.0


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, client: anthropic.Anthropic | None = None) -> None:
        self.model = model
        # El peor caso (2 intentos x 20 s) queda debajo de API_TIMEOUT_SECONDS del front (45 s),
        # así un LLM lento degrada al fallback del mock en lugar de una página de error.
        self.client = client or anthropic.Anthropic(max_retries=1, timeout=REQUEST_TIMEOUT_SECONDS)

    def extract(self, transcript: str, ctx: ExtractionContext) -> RawExtraction:
        user = build_extraction_user_message(transcript, ctx.similar_cases, ctx.candidate_questions)
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=MAX_TOKENS,
                # En esta familia de modelos el thinking siempre está activo y cuenta contra max_tokens;
                # la extracción necesita poco razonamiento, así que effort bajo la mantiene rápida y barata.
                output_config={"effort": EFFORT},
                system=EXTRACTION_PROMPT.system,
                messages=[{"role": "user", "content": user}],
                output_format=RawExtraction,
                # Fallback del lado del servidor si el modelo principal rechaza el pedido.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as exc:
            raise ProviderError(f"Rate limit del proveedor LLM: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Error del proveedor LLM ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("Sin conexión con el proveedor LLM") from exc
        except anthropic.APIError as exc:
            raise ProviderError(f"Error del proveedor LLM: {exc.__class__.__name__}") from exc
        except (pydantic.ValidationError, ValueError) as exc:
            # El SDK valida el JSON contra RawExtraction al parsear, así que un cuerpo malformado
            # o truncado por max_tokens falla acá, antes de poder mirar stop_reason.
            raise ProviderError("Respuesta del modelo inválida o truncada") from exc

        if response.stop_reason == "refusal":
            raise ProviderError("El modelo rechazó la solicitud")
        if response.stop_reason == "max_tokens":
            raise ProviderError("Respuesta truncada (max_tokens)")
        if response.parsed_output is None:
            raise ProviderError("Respuesta sin JSON válido")
        return response.parsed_output
