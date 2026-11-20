"""Provider determinista basado en reglas (LLM_PROVIDER=mock). Offline y gratuito.

Es simple a propósito: regex para la dirección, vecinos más cercanos sobre el
catálogo para el tipo de incidente, solapamiento de palabras para el checklist y un
pequeño conjunto de señales de alarma que escalan la prioridad.
"""

from __future__ import annotations

import re

from services.providers.base import ExtractionContext
from services.models import Category, ChecklistAnswer, ExtractedField, Priority, RawExtraction, ReferenceCase
from services.nlp.text import fold, tokens

_UP = r"A-ZÁÉÍÓÚÑ"
_WORD = rf"[{_UP}0-9][\wáéíóúñ]*"
_ABBR = r"(?:Av\.?|Avenida|Gral\.|Pte\.|Dr\.)\s+"
_NAME = rf"(?:{_ABBR})?[{_UP}][\wáéíóúñ]*(?:\s+(?:de\s+)?{_WORD}){{0,3}}"
_LEADING_NOISE = re.compile(r"^(?:En|Es|La|El|Los|Las|Estoy|Acá|Hay)\s+")

STREET_NUMBER_RE = re.compile(rf"({_NAME})\s+(?:al\s+)?(\d{{3,5}})\b")
CASI_RE = re.compile(rf"\b(?:casi|esquina)\s+({_NAME})")
ENTRE_RE = re.compile(rf"\bentre\s+({_NAME})\s+y\s+({_NAME})")
CORNER_RE = re.compile(rf"(?:\b(?:en|de)|,)\s+({_NAME})\s+y\s+({_NAME})")

# Subconjunto de barrios de CABA; alcanza para el prototipo.
NEIGHBORHOODS = [
    "Agronomía", "Almagro", "Balvanera", "Barracas", "Belgrano", "Boedo", "Caballito",
    "Chacarita", "Coghlan", "Colegiales", "Constitución", "Flores", "Floresta", "La Boca",
    "Liniers", "Mataderos", "Monserrat", "Nueva Pompeya", "Núñez", "Palermo",
    "Parque Patricios", "Puerto Madero", "Recoleta", "Retiro", "Saavedra", "San Cristóbal",
    "San Nicolás", "San Telmo", "Villa Crespo", "Villa Devoto", "Villa Lugano",
    "Villa Soldati", "Soldati", "Villa Urquiza",
]

# Léxico de raíces por categoría: complementa la votación por vecinos más cercanos,
# que es débil con un catálogo de 30 filas donde la mayoría de las subcategorías
# aparece una sola vez.
CATEGORY_LEXICON: dict[Category, list[str]] = {
    Category.INCENDIO_RESCATE: ["fuego", "incend", "llama", "humo", "bomber", "prend", "ascensor", "rescat", "explot"],
    Category.ACCIDENTE_VIAL: ["choc", "colisi", "moto", "taxi", "colectivo", "camion", "atropell", "volc", "autopista", "ciclist"],
    Category.EMERGENCIA_MEDICA: ["same", "paciente", "respir", "desmay", "convuls", "alergi", "fractur", "dolor", "concien", "ambulan"],
    Category.DEFENSA_CIVIL: ["arbol", "derrumb", "inund", "anega", "marquesin", "medianer", "temporal", "fuga", "gas"],
    Category.SERVICIOS_PUBLICOS: ["semafor", "cable", "socavon", "pozo", "agua", "luz", "cloac", "poste"],
    Category.CONVIVENCIA_SEGURIDAD: ["pelea", "perro", "robo", "disturb", "botella", "agresi", "arma"],
}

# Señales de alarma -> P1 sin importar el vecino más cercano.
P1_FLAGS = [
    "no respira", "no responde", "no se mueve", "atrapad", "quedo adentro", "labios morados",
    "convulsion", "se le esta cerrando la garganta", "exploto", "explosion", "chispeando",
    "olor a gas", "fuga de gas", "inconsciente", "sangrando mucho", "humo negro",
    # materiales peligrosos: un derrame de combustible es un incendio en potencia
    "cisterna", "combustible", "gasoil", "nafta", "derrame",
]


def _caller_text(transcript: str) -> str:
    """Descarta el saludo del operador; la dirección es lo que dice el llamante."""
    parts = re.split(r"Llamante\s*:", transcript, maxsplit=1)
    return parts[1] if len(parts) == 2 else transcript


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[\.\!\?,])\s+", text) if s.strip()]


class MockProvider:
    name = "mock"

    def extract(self, transcript: str, ctx: ExtractionContext) -> RawExtraction:
        caller = _caller_text(transcript)
        street, street_number, intersection = self._address(caller)
        neighborhood = self._neighborhood(caller)

        category = self._classify(transcript, ctx)
        anchor = ctx.anchor_for(category)
        top: ReferenceCase | None = anchor[0] if anchor else None
        priority = top.priority if top else Priority.P3
        justification = (
            f"Prioridad del caso de referencia más similar ({top.id})." if top else "Sin referencia."
        )
        flag = next((f for f in P1_FLAGS if f in fold(transcript)), None)
        if flag and priority != Priority.P1:
            priority = Priority.P1
            justification = f"Escalado a P1 por señal de alarma en el relato: '{flag}'."

        return RawExtraction(
            street=street,
            street_number=street_number,
            intersection=intersection,
            neighborhood=neighborhood,
            category=category,
            subcategory=top.subcategory if top else "Sin subcategoría de referencia",
            priority=priority,
            priority_rationale=justification,
            checklist=[self.answer_question(q, transcript) for q in ctx.candidate_questions],
            risks=list(top.risks) if top else [],
            summary=_sentences(caller)[0][:200] if caller.strip() else "",
        )

    # --------------------------------------------------------------- auxiliares
    @staticmethod
    def _classify(transcript: str, ctx: ExtractionContext) -> Category:
        words = re.findall(r"[a-z0-9]+", fold(transcript))
        scores: dict[Category, float] = {cat: 0.0 for cat in Category}
        for cat, stems in CATEGORY_LEXICON.items():
            scores[cat] += sum(1.0 for w in words for st in stems if w.startswith(st))
        for case, sim in ctx.similar_cases:
            scores[case.category] += 4.0 * sim
        return max(scores, key=lambda c: scores[c])

    @staticmethod
    def _address(text: str) -> tuple[ExtractedField, ExtractedField, ExtractedField]:
        street = street_number = inter = ExtractedField()
        if m := STREET_NUMBER_RE.search(text):
            street = ExtractedField(value=_LEADING_NOISE.sub("", m.group(1).strip()), evidence=m.group(0))
            street_number = ExtractedField(value=m.group(2), evidence=m.group(0))
        if m := ENTRE_RE.search(text):
            inter = ExtractedField(value=f"{m.group(1)} y {m.group(2)}", evidence=m.group(0))
        elif m := CASI_RE.search(text):
            inter = ExtractedField(value=m.group(1).strip(), evidence=m.group(0))
        if (m := CORNER_RE.search(text)) and (street.value is None or inter.value is None):
            if street.value is None:
                street = ExtractedField(value=m.group(1).strip(), evidence=m.group(0))
                inter = ExtractedField(value=m.group(2).strip(), evidence=m.group(0))
            else:
                inter = ExtractedField(value=m.group(2).strip(), evidence=m.group(0))
        return street, street_number, inter

    @staticmethod
    def _neighborhood(text: str) -> ExtractedField:
        # Exige "en <barrio>" / "barrio <barrio>" para evitar falsos positivos ("espuma en la boca").
        folded = fold(text)
        for neighborhood in sorted(NEIGHBORHOODS, key=len, reverse=True):
            name = fold(neighborhood)
            if m := re.search(rf"\b(?:en|barrio(?: de)?)\s+{re.escape(name)}\b", folded):
                if name == "la boca" and not m.group(0).startswith("barrio"):
                    continue  # "espuma en la boca" no es un barrio
                return ExtractedField(value=neighborhood, evidence=text[m.start():m.end()])
        return ExtractedField()

    @staticmethod
    def answer_question(question: str, transcript: str) -> ChecklistAnswer:
        caller = _caller_text(transcript)
        q_stems = {t[:5] for t in tokens(question)}
        best, best_overlap = None, 0.0
        for sentence in _sentences(caller):
            overlap = len(q_stems & {t[:5] for t in tokens(sentence)}) / (len(q_stems) or 1)
            if overlap > best_overlap:
                best, best_overlap = sentence, overlap
        answered = best is not None and best_overlap >= 0.3
        return ChecklistAnswer(
            question=question,
            answered=answered,
            answer=best if answered else None,
            evidence=best if answered else None,
        )
