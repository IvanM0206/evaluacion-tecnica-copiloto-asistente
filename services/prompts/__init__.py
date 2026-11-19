"""Prompts de los providers LLM, fuera del código del provider.

- `base`: piezas de armado (`PromptSection`, `PromptTemplate`).
- `sections`: secciones reutilizables con nombre (rol, reglas de grounding, checklist, ...).
- un módulo por tarea (`extraction`): el template más su constructor de mensaje de usuario.

Una tarea, skill o agente nuevo es un módulo nuevo que compone secciones existentes con
las propias, así las reglas del dominio (grounding, contexto CABA) se escriben una sola vez.
Importar desde `services.prompts`.
"""

from __future__ import annotations

from services.prompts.base import PromptSection, PromptTemplate
from services.prompts.extraction import EXTRACTION_PROMPT, build_extraction_user_message

__all__ = ["EXTRACTION_PROMPT", "PromptSection", "PromptTemplate", "build_extraction_user_message"]
