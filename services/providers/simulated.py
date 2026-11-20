"""Simulación del LLM (ayuda para la demo): el mock determinista más salidas de ejemplo fijas.

Algunas funciones solo existen con un LLM real (preguntas extra sugeridas). Con
`simulate_llm=true` el operador puede ver cómo se ve el panel con ellas, sin key ni red.
Las salidas son fijas por categoría y la sugerencia queda marcada `simulated`, así la UI
nunca las hace pasar por salida de un modelo.
"""

from __future__ import annotations

from services.models import Category, RawExtraction
from services.providers.base import ExtractionContext
from services.providers.mock import MockProvider

SIMULATED_QUESTIONS: dict[Category, list[str]] = {
    Category.INCENDIO_RESCATE: [
        "¿Hay garrafas o tubos de gas cerca del fuego?",
        "¿Alguien quedó en pisos superiores, baños o depósitos?",
        "¿El humo está pasando a departamentos o locales linderos?",
    ],
    Category.EMERGENCIA_MEDICA: [
        "¿La persona toma alguna medicación o tiene antecedentes conocidos?",
        "¿Hay alguien con ella que sepa primeros auxilios?",
        "¿Puede alguien esperar a la ambulancia en la puerta para guiarla?",
    ],
    Category.ACCIDENTE_VIAL: [
        "¿Algún vehículo pierde combustible o sale humo del motor?",
        "¿Hay heridos en la calzada con tránsito todavía circulando?",
        "¿Hay chicos o embarazadas entre los involucrados?",
    ],
    Category.DEFENSA_CIVIL: [
        "¿Hay personas debajo o muy cerca de la estructura afectada?",
        "¿Se cortó la luz o el gas en la cuadra?",
        "¿Alguien está desviando a los peatones?",
    ],
    Category.SERVICIOS_PUBLICOS: [
        "¿Hay cables o agua en contacto con la vereda por donde pasa gente?",
        "¿Desde hace cuánto tiempo está así?",
        "¿Afecta a algún hospital, escuela o geriátrico de la cuadra?",
    ],
    Category.CONVIVENCIA_SEGURIDAD: [
        "¿Alguna de las personas tiene armas u objetos contundentes?",
        "¿Hay heridos?",
        "¿Puede describir a las personas involucradas y hacia dónde van?",
    ],
}


class SimulatedLLMProvider:
    name = "simulación LLM"

    def __init__(self) -> None:
        self._mock = MockProvider()

    def extract(self, transcript: str, ctx: ExtractionContext) -> RawExtraction:
        raw = self._mock.extract(transcript, ctx)
        return raw.model_copy(update={"suggested_questions": list(SIMULATED_QUESTIONS.get(raw.category, []))})
