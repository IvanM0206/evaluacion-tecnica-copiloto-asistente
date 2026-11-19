"""services/nlp: utilidades de texto, protección de grounding, retrieval y normalización de calles."""

from __future__ import annotations

import pytest

from services.models import Category, ReferenceCase
from services.nlp.normalization import StreetGazetteer, canonical_street
from services.nlp.retrieval import CaseRetriever
from services.nlp.text import fold, is_grounded, tokens

TRANSCRIPT = (
    "Operador: 911, ¿dónde es su urgencia? Llamante: En la pizzería de Av. Corrientes 1540 "
    "casi Montevideo, se prendió fuego la campana de la cocina y adentro quedó el cocinero!"
)


# -------------------------------------------------------------------- texto
class TestFold:
    def test_lowercases_and_strips_accents(self) -> None:
        assert fold("Castañares ÁRBOL Pompeya") == "castanares arbol pompeya"

    def test_is_idempotent(self) -> None:
        assert fold(fold("Núñez")) == "nunez"


class TestTokens:
    def test_drops_stopwords_short_tokens_and_speaker_labels(self) -> None:
        result = tokens("Operador: Hola, ¿hay humo en el 5º piso? Llamante: Sí, mucho humo negro")
        assert "operador" not in result and "llamante" not in result
        assert "hay" not in result and "en" not in result
        assert result.count("humo") == 2
        assert "negro" in result and "piso" in result

    def test_tokens_are_folded(self) -> None:
        assert tokens("Explosión en Castañares") == ["explosion", "castanares"]


class TestIsGrounded:
    def test_literal_evidence_is_grounded(self) -> None:
        assert is_grounded("Av. Corrientes 1540", TRANSCRIPT)

    def test_accents_case_and_surrounding_punctuation_are_ignored(self) -> None:
        assert is_grounded('"av. CORRIENTES 1540."', TRANSCRIPT)

    def test_small_paraphrase_above_threshold_is_grounded(self) -> None:
        # Un carácter de más en una cita larga: bloque literal más largo >= 85 % de la evidencia.
        assert is_grounded("se prendió fuego la campana de la cocinaa", TRANSCRIPT)

    def test_invented_evidence_is_rejected(self) -> None:
        assert not is_grounded("Av. Santa Fe 3200 esquina Coronel Díaz", TRANSCRIPT)

    def test_partially_invented_evidence_below_threshold_is_rejected(self) -> None:
        assert not is_grounded("Av. Corrientes 9999 frente a la plaza", TRANSCRIPT)

    @pytest.mark.parametrize("evidence", [None, "", "  .,  "])
    def test_empty_evidence_is_not_grounded(self, evidence: str | None) -> None:
        assert not is_grounded(evidence, TRANSCRIPT)


# ---------------------------------------------------------------- retrieval
class TestCaseRetriever:
    def test_leave_one_out_excludes_identical_transcript(self, reference_cases: list[ReferenceCase]) -> None:
        retriever = CaseRetriever(reference_cases)
        query = reference_cases[0]
        results = retriever.search(query.transcript, k=len(reference_cases))
        assert query.id not in {case.id for case, _ in results}
        assert len(results) == len(reference_cases) - 1

    def test_leave_one_out_is_accent_and_case_insensitive(self, reference_cases: list[ReferenceCase]) -> None:
        retriever = CaseRetriever(reference_cases)
        query = reference_cases[0]
        variant = fold(query.transcript).upper() + "   "
        assert query.id not in {case.id for case, _ in retriever.search(variant, k=30)}

    def test_without_exclusion_identical_case_ranks_first(self, reference_cases: list[ReferenceCase]) -> None:
        retriever = CaseRetriever(reference_cases)
        query = reference_cases[4]
        (top, score), *_ = retriever.search(query.transcript, k=3, exclude_exact=False)
        assert top.id == query.id
        assert score == pytest.approx(1.0, abs=0.35)

    def test_results_are_sorted_and_limited_to_k(self, reference_cases: list[ReferenceCase]) -> None:
        results = CaseRetriever(reference_cases).search("se prendió fuego, hay humo negro, manden bomberos", k=3)
        scores = [score for _, score in results]
        assert len(results) == 3
        assert scores == sorted(scores, reverse=True)
        assert results[0][0].category == Category.INCENDIO_RESCATE

    def test_unrelated_query_scores_zero(self, reference_cases: list[ReferenceCase]) -> None:
        results = CaseRetriever(reference_cases).search("xyzzy qwerty", k=2)
        assert all(score == 0 for _, score in results)

    def test_empty_catalog_returns_nothing(self) -> None:
        assert CaseRetriever([]).search("fuego en la cocina") == []


# ------------------------------------------------------------ normalización
class TestCanonicalStreet:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Avenida Corrientes", "Av. Corrientes"),
            ("av Corrientes", "Av. Corrientes"),
            ("Av. Corrientes", "Av. Corrientes"),
            ("Avda Rivadavia", "Av. Rivadavia"),
            ("AU 25 de Mayo", "Autopista 25 de Mayo"),
            ("  Billinghurst  ", "Billinghurst"),
            ("", ""),
        ],
    )
    def test_prefix_normalization(self, raw: str, expected: str) -> None:
        assert canonical_street(raw) == expected


class TestStreetGazetteer:
    @pytest.fixture
    def gazetteer(self) -> StreetGazetteer:
        return StreetGazetteer(["Av. Raúl Scalabrini Ortiz", "Billinghurst", "Vera y Velasco", "Av. Corrientes"])

    def test_exact_match_ignores_accents_case_and_av_prefix(self, gazetteer: StreetGazetteer) -> None:
        assert gazetteer.match("billinghurst") == "Billinghurst"
        assert gazetteer.match("Avenida Corrientes") == "Av. Corrientes"
        assert gazetteer.match("RAUL SCALABRINI ORTIZ") == "Av. Raúl Scalabrini Ortiz"

    def test_intersections_are_split_into_streets(self, gazetteer: StreetGazetteer) -> None:
        assert gazetteer.match("Velasco") == "Velasco"
        assert gazetteer.match("Vera") == "Vera"

    def test_suffix_match(self, gazetteer: StreetGazetteer) -> None:
        assert gazetteer.match("Scalabrini Ortiz") == "Av. Raúl Scalabrini Ortiz"

    def test_fuzzy_match_tolerates_typos(self, gazetteer: StreetGazetteer) -> None:
        assert gazetteer.match("Scalabrini Ortis") == "Av. Raúl Scalabrini Ortiz"
        assert gazetteer.match("Bilinghurst") == "Billinghurst"

    @pytest.mark.parametrize("raw", [None, "", "Juramento"])
    def test_unknown_or_empty_returns_none(self, gazetteer: StreetGazetteer, raw: str | None) -> None:
        assert gazetteer.match(raw) is None
