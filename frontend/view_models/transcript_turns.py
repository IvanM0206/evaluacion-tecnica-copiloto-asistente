"""Vista de solo lectura de una transcripción, partida en turnos Operador / Llamante."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

_SPEAKER_RE = re.compile(r"\b(Operadora?|Llamante)\s*:\s*", re.IGNORECASE)


class TranscriptTurnVM(BaseModel):
    speaker: str
    text: str

    @property
    def role(self) -> Literal["operador", "llamante", "otro"]:
        key = self.speaker.lower()
        if key.startswith("operador"):
            return "operador"
        return "llamante" if key == "llamante" else "otro"


def split_turns(transcript: str) -> list[TranscriptTurnVM]:
    """Parte 'Operador: … Llamante: …' en turnos para una vista legible de solo lectura."""
    parts = _SPEAKER_RE.split(transcript)
    turns: list[TranscriptTurnVM] = []
    if head := parts[0].strip():
        turns.append(TranscriptTurnVM(speaker="", text=head))
    for speaker, text in zip(parts[1::2], parts[2::2], strict=True):
        if text := text.strip():
            turns.append(TranscriptTurnVM(speaker=speaker.capitalize(), text=text))
    return turns
