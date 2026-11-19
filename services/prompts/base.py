"""Piezas de armado de prompts: secciones con nombre que se componen en templates versionados."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptSection:
    """Un bloque de instrucciones autocontenido que pueden compartir varios prompts."""

    key: str  # identificador estable, útil para logs/evals ("grounding", "checklist", ...)
    body: str

    def render(self) -> str:
        return self.body.strip()


@dataclass(frozen=True)
class PromptTemplate:
    """Un system prompt formado por secciones ordenadas. Subir `version` cuando cambia el texto,
    así las corridas de evaluación se pueden comparar contra el prompt que las produjo."""

    name: str
    version: str
    sections: tuple[PromptSection, ...]

    @property
    def system(self) -> str:
        return "\n\n".join(section.render() for section in self.sections)

    @property
    def section_keys(self) -> tuple[str, ...]:
        return tuple(section.key for section in self.sections)

    def with_sections(self, *extra: PromptSection, name: str | None = None, version: str | None = None) -> PromptTemplate:
        """Deriva un template nuevo (p. ej. un agente o skill) reusando estas secciones más `extra`."""
        return PromptTemplate(name=name or self.name, version=version or self.version, sections=self.sections + extra)
