"""Utilidades de texto: normalización sin acentos, tokenización y chequeos de grounding."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_STOPWORDS = {
    "a", "al", "algo", "ante", "con", "de", "del", "el", "en", "es", "esta", "este", "hay",
    "la", "las", "le", "lo", "los", "me", "mi", "muy", "no", "o", "para", "pero", "por",
    "que", "se", "si", "sin", "su", "un", "una", "uno", "y", "ya", "ahi", "aca", "como",
    "operador", "llamante", "hola", "buenas", "buen", "dia", "tardes", "noches", "favor",
}


def fold(text: str) -> str:
    """Pasa a minúsculas y quita acentos para que 'Castañares' == 'castanares'."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", fold(text)) if t not in _STOPWORDS and len(t) > 2]


def is_grounded(evidence: str | None, transcript: str, threshold: float = 0.85) -> bool:
    """True si `evidence` aparece (casi) literal en la transcripción.

    Es la principal protección anti-alucinación: un valor cuya cita no se encuentra
    en lo que realmente dijo el llamante se muestra al operador como 'no verificado'.
    """
    if not evidence:
        return False
    ev, tr = fold(evidence).strip(" .,\"'"), fold(transcript)
    if not ev:
        return False
    if ev in tr:
        return True
    # Tolera pequeñas paráfrasis / diferencias de puntuación.
    matcher = SequenceMatcher(None, tr, ev, autojunk=False)
    match = matcher.find_longest_match(0, len(tr), 0, len(ev))
    return match.size / len(ev) >= threshold
