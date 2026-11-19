from __future__ import annotations

import logging
import re

from services.catalog_service import CatalogService
from services.models import (
    ChecklistItem,
    CopilotSuggestion,
    ExtractedField,
    GroundedField,
    RawExtraction,
    ReferenceCase,
    SimilarCase,
)
from services.nlp.normalization import StreetGazetteer, canonical_street
from services.nlp.retrieval import CaseRetriever
from services.nlp.text import fold, is_grounded
from services.providers import ExtractionContext, ExtractionProvider, MockProvider, ProviderError

log = logging.getLogger(__name__)

MIN_SIMILARITY = 0.2  # por debajo de esto el tipo de incidente es una suposición
MAX_QUESTIONS = 8


class CopilotService:
    """Orquestador: retrieval -> extracción por provider -> grounding/validación -> sugerencia."""

    def __init__(self, catalog: CatalogService, provider: ExtractionProvider) -> None:
        self._catalog_service = catalog
        self.provider = provider
        self._fallback = MockProvider()
        self._retriever: CaseRetriever | None = None
        self._gazetteer: StreetGazetteer | None = None
        catalog.on_change(self.reset_indexes)

    def reset_indexes(self) -> None:
        """Descarta los índices de retrieval/calles; se reconstruyen en el próximo análisis."""
        self._retriever = None
        self._gazetteer = None

    # Los índices se construyen lazy: al importar, la DB puede no estar migrada/cargada.
    @property
    def catalog(self) -> list[ReferenceCase]:
        return self._catalog_service.cases()

    # Leer `self.catalog` primero permite que el catálogo detecte cambios y resetee los índices.
    @property
    def retriever(self) -> CaseRetriever:
        cases = self.catalog
        if self._retriever is None:
            self._retriever = CaseRetriever(cases)
        return self._retriever

    @property
    def gazetteer(self) -> StreetGazetteer:
        cases = self.catalog
        if self._gazetteer is None:
            self._gazetteer = StreetGazetteer([c.street for c in cases] + [c.intersection for c in cases])
        return self._gazetteer

    # ----------------------------------------------------------------- público
    def analyze(self, transcript: str) -> CopilotSuggestion:
        similar = self.retriever.search(transcript, k=5)
        ctx = ExtractionContext(
            similar_cases=similar,
            candidate_questions=self._candidate_questions(similar),
            known_streets=[c.street for c in self.catalog],
        )

        warnings: list[str] = []
        provider_name = self.provider.name
        try:
            raw = self.provider.extract(transcript, ctx)
        except ProviderError as exc:
            log.warning("provider %s failed: %s", self.provider.name, exc)
            warnings.append(f"Proveedor IA no disponible ({exc}). Se usó el modo reglas.")
            raw = self._fallback.extract(transcript, ctx)
            provider_name = f"{self._fallback.name} (fallback)"

        return self._build_suggestion(transcript, raw, ctx, provider_name, warnings)

    # -------------------------------------------------------------- auxiliares
    @staticmethod
    def _candidate_questions(similar: list[tuple[ReferenceCase, float]]) -> list[str]:
        """Preguntas de protocolo de la categoría más probable (por similitud sumada).

        Mezclar preguntas de distintos tipos de incidente confunde al operador, así que
        el conjunto se toma de (como máximo) los dos mejores casos de una sola categoría.
        """
        if not similar:
            return []
        votes: dict[str, float] = {}
        for case, score in similar:
            votes[case.category] = votes.get(case.category, 0.0) + score
        best = max(votes, key=lambda cat: votes[cat])
        return CopilotService._questions_of([c for c, _ in similar if c.category == best][:2])

    @staticmethod
    def _questions_of(cases: list[ReferenceCase]) -> list[str]:
        seen: dict[str, str] = {}
        for case in cases:
            for q in case.mandatory_questions + case.pending_questions:
                seen.setdefault(fold(q), q)
        return list(seen.values())[:MAX_QUESTIONS]

    def _ground(self, field: ExtractedField, transcript: str, street: bool = False) -> GroundedField:
        if field.value is None:
            grounded = False
        elif field.evidence:
            # La cita tiene que estar en la llamada Y contener efectivamente el valor
            # (rechaza p. ej. value="1243" con evidence="al 1234").
            grounded = is_grounded(field.evidence, transcript) and is_grounded(field.value, field.evidence)
        else:
            grounded = is_grounded(field.value, transcript)
        normalized = None
        if street and field.value:
            normalized = self.gazetteer.match(field.value) or canonical_street(field.value)
        # Un valor encontrado literal en la llamada es su propia evidencia (nunca grounded sin evidencia).
        evidence = field.evidence or (field.value if grounded else None)
        return GroundedField(
            value=field.value, evidence=evidence, grounded=grounded, normalized=normalized
        )

    def _build_suggestion(
        self,
        transcript: str,
        raw: RawExtraction,
        ctx: ExtractionContext,
        provider_name: str,
        warnings: list[str],
    ) -> CopilotSuggestion:
        street = self._ground(raw.street, transcript, street=True)
        street_number = self._ground(raw.street_number, transcript)
        intersection = self._ground(raw.intersection, transcript)
        neighborhood = self._ground(raw.neighborhood, transcript)

        # Anchor = caso de referencia más similar de la categoría *final*. De él salen
        # las preguntas de protocolo, las instrucciones pre-arribo y los recursos, así
        # el panel nunca mezcla protocolos de distintos tipos de incidente.
        anchor, anchor_score = next(
            ((c, sc) for c, sc in ctx.similar_cases if c.category == raw.category), (None, 0.0)
        )
        answers = list(raw.checklist)
        questions = ctx.candidate_questions
        if anchor and not {fold(q) for q in self._questions_of([anchor])} & {fold(q) for q in questions}:
            # El provider eligió una categoría distinta a la del protocolo preseleccionado.
            questions = self._questions_of([anchor])
            answers = [MockProvider.answer_question(q, transcript) for q in questions]
            warnings.append("Checklist recalculado para la categoría final (respuestas por reglas).")
        if anchor is None:
            warnings.append("Sin caso de referencia para esta categoría: aplicar protocolo general.")

        # Solo sobreviven las preguntas de protocolo del catálogo; las inventadas se descartan.
        allowed = {fold(q): q for q in questions}
        by_question = {fold(a.question): a for a in answers}
        checklist: list[ChecklistItem] = []
        for key, question in allowed.items():
            ans = by_question.get(key)
            grounded = bool(ans and ans.answered and is_grounded(ans.evidence, transcript))
            checklist.append(
                ChecklistItem(
                    question=question,
                    answered=bool(ans and ans.answered),
                    answer=ans.answer if ans else None,
                    evidence=ans.evidence if ans else None,
                    grounded=grounded,
                )
            )
        if dropped := set(by_question) - set(allowed):
            warnings.append(f"Se descartaron {len(dropped)} preguntas no pertenecientes al protocolo.")

        if not street.value:
            warnings.append("No se detectó la calle: confirmar dirección con el llamante.")
        elif not street.grounded:
            warnings.append("La calle sugerida no figura literalmente en el relato: verificar.")
        if not street_number.value and not intersection.value:
            warnings.append("Falta altura o intersección para ubicar el hecho.")
        if anchor_score < MIN_SIMILARITY:
            warnings.append("Tipificación con baja similitud a casos conocidos: revisar categoría.")
        if anchor and raw.priority != anchor.priority:
            warnings.append(
                f"La prioridad sugerida ({raw.priority}) difiere del caso de referencia "
                f"{anchor.id} ({anchor.priority})."
            )

        instructions = (
            [s.strip() for s in re.split(r"(?<=\.)\s+", anchor.pre_arrival_instructions) if s.strip()]
            if anchor
            else []
        )

        return CopilotSuggestion(
            provider=provider_name,
            street=street,
            street_number=street_number,
            intersection=intersection,
            neighborhood=neighborhood,
            category=raw.category,
            subcategory=raw.subcategory,
            priority=raw.priority,
            priority_rationale=raw.priority_rationale,
            checklist=checklist,
            pre_arrival_instructions=instructions,
            risks=raw.risks,
            suggested_resources=anchor.resources if anchor else "",
            summary=raw.summary,
            confidence=self._confidence(street.grounded, street_number.grounded or intersection.grounded, anchor_score, checklist, provider_name),
            warnings=warnings,
            similar_cases=[
                SimilarCase(id=c.id, subcategory=c.subcategory, priority=c.priority, score=round(s, 3))
                for c, s in ctx.similar_cases
            ],
        )

    @staticmethod
    def _confidence(
        street_ok: bool, location_ok: bool, top_score: float, checklist: list[ChecklistItem], provider: str
    ) -> float:
        """Puntaje heurístico de certeza que se muestra al operador (no es una probabilidad calibrada)."""
        answered = [c for c in checklist if c.answered]
        grounded_ratio = (sum(c.grounded for c in answered) / len(answered)) if answered else 1.0
        score = (
            0.30 * street_ok
            + 0.15 * location_ok
            + 0.35 * min(top_score / 0.35, 1.0)
            + 0.20 * grounded_ratio
        )
        if provider.startswith("mock"):
            score *= 0.9  # las reglas son más frágiles que un LLM ante redacciones nuevas
        return round(min(max(score, 0.0), 1.0), 2)
