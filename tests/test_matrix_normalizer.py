"""Tests for the v0.7.0 MiniLM matrix-name fuzzy normaliser.

Two tiers:

* **Always-on tests** — run on the base install. Exercise the bundled
  UBERON term list, the no-ml fallback path, the redu integration when
  `normalize_matrix=False`, and the import-guard in `_maybe_enrich_matrix`.

* **`[ml]`-gated tests** — auto-skip when `sentence-transformers` is not
  importable. Cover the real MiniLM forward pass + embedding cache.
"""
from __future__ import annotations

import importlib.util
import json
from importlib.resources import files

import pytest

from indicium_adapters_metabolomics._matrix_normalizer import (
    DEFAULT_THRESHOLD,
    MODEL_NAME,
    MatrixNormalizer,
    _load_uberon_terms,
    _term_phrases,
)
from indicium_adapters_metabolomics.redu import redu_sample_to_claims

_HAS_ML = importlib.util.find_spec("sentence_transformers") is not None
ml_only = pytest.mark.skipif(not _HAS_ML, reason="sentence-transformers not installed")


# --- always-on tests ------------------------------------------------------

def test_uberon_terms_file_loads_with_curated_entries():
    terms = _load_uberon_terms()
    assert len(terms) >= 40, "seed list should ship ≥40 UBERON/PO terms"
    curies = {t["curie"] for t in terms}
    # Spot-check the headline biofluids — these must be present.
    assert "UBERON:0001988" in curies   # feces
    assert "UBERON:0001088" in curies   # urine
    assert "UBERON:0001969" in curies   # blood plasma
    assert "UBERON:0000178" in curies   # blood
    # And the PO plant matrices (EMI/ENPKG uses these).
    assert "PO:0009025" in curies       # leaf


def test_term_phrases_includes_label_and_synonyms():
    term = {"curie": "UBERON:0001988", "label": "feces",
            "synonyms": ["stool", "fecal"]}
    assert _term_phrases(term) == ["feces", "stool", "fecal"]


def test_term_phrases_skips_empty_synonyms():
    term = {"curie": "X:1", "label": "thing", "synonyms": ["", None, "real"]}
    assert _term_phrases(term) == ["thing", "real"]


def test_uberon_terms_have_no_bare_synonym_strings():
    """Every term entry must declare 'curie' + 'label'; rows without those
    (e.g. the `_comment_plant` marker) are filtered by _load_uberon_terms."""
    raw = json.loads(
        files("indicium_adapters_metabolomics.data")
        .joinpath("_uberon_terms.json")
        .read_text(encoding="utf-8")
    )
    for row in raw.get("terms", []):
        if "curie" in row:
            assert "label" in row, f"row missing label: {row}"


def test_normalizer_constructor_is_cheap_no_model_load():
    """Instantiating MatrixNormalizer must not download the model."""
    n = MatrixNormalizer()
    assert n._model is None
    assert n._embeddings is None
    # Default knobs are exported as module constants for tests.
    assert n.threshold == DEFAULT_THRESHOLD
    assert n.model_name == MODEL_NAME


def test_normalizer_normalize_empty_returns_none():
    n = MatrixNormalizer()
    assert n.normalize("") is None
    assert n.normalize("   ") is None


def test_normalizer_normalize_returns_none_when_ml_missing(monkeypatch):
    """When sentence-transformers isn't importable, normalize() is a no-op."""
    n = MatrixNormalizer()

    # Force `available` to False even when ml IS installed locally.
    monkeypatch.setattr(MatrixNormalizer, "available",
                        property(lambda self: False))
    assert n.normalize("feces") is None


def test_redu_normalize_matrix_default_off_preserves_v060_behavior():
    """Default (normalize_matrix=False) emits no ontology_terms when ReDU's
    own UBERON CURIE column is absent."""
    sample = {"UBERONBodyPartName": "stool"}  # no UBERONOntologyIndex
    claims = redu_sample_to_claims(sample, "study:s1")
    matrix = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert matrix["object"] == "stool"
    assert "ontology_terms" not in matrix
    assert "evidence" not in matrix


def test_redu_normalize_matrix_silently_skips_when_extra_missing(monkeypatch):
    """If `normalize_matrix=True` but the [ml] extra is not installed, the
    claim is unchanged — no exception, no log spam."""
    # Make the import in _maybe_enrich_matrix raise ImportError.
    import builtins
    real_import = builtins.__import__

    def boom(name, *a, **k):
        if name == "indicium_adapters_metabolomics._matrix_normalizer":
            raise ImportError("simulated missing extra")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", boom)
    sample = {"UBERONBodyPartName": "stool"}
    claims = redu_sample_to_claims(sample, "study:s1", normalize_matrix=True)
    matrix = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert "ontology_terms" not in matrix


def test_redu_normalize_matrix_skips_when_uberon_curie_already_present():
    """If ReDU's curated CURIE is in the row, MiniLM is not consulted —
    the curated value wins (v0.6.x semantics)."""
    sample = {
        "UBERONBodyPartName": "stool",
        "UBERONOntologyIndex": "UBERON:0001988",  # already present
    }
    claims = redu_sample_to_claims(sample, "study:s1", normalize_matrix=True)
    matrix = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert matrix["ontology_terms"]["object"] == "UBERON:0001988"
    # Score isn't added because the normaliser path wasn't taken.
    assert "evidence" not in matrix


def test_redu_normalize_matrix_normalize_function_returning_none_is_a_noop(monkeypatch):
    """A confident-but-below-threshold match (normalize_matrix returns None)
    must leave the claim unchanged — no zombie ontology_terms key."""
    from indicium_adapters_metabolomics import _matrix_normalizer

    monkeypatch.setattr(_matrix_normalizer, "normalize_matrix",
                        lambda text: None)
    sample = {"UBERONBodyPartName": "aircraft engine"}
    claims = redu_sample_to_claims(sample, "study:s1", normalize_matrix=True)
    matrix = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert "ontology_terms" not in matrix


def test_redu_normalize_matrix_applies_curie_and_score(monkeypatch):
    """Stubbed match: the claim picks up CURIE + rounded score."""
    from indicium_adapters_metabolomics import _matrix_normalizer

    monkeypatch.setattr(_matrix_normalizer, "normalize_matrix",
                        lambda text: ("feces", "UBERON:0001988", 0.812345))
    sample = {"UBERONBodyPartName": "stool"}
    claims = redu_sample_to_claims(sample, "study:s1", normalize_matrix=True)
    matrix = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert matrix["object"] == "stool"  # literal preserved
    assert matrix["ontology_terms"]["object"] == "UBERON:0001988"
    assert matrix["evidence"]["matrix_match_score"] == 0.8123  # rounded to 4dp


def test_redu_normalize_matrix_also_works_on_sample_type_fallback(monkeypatch):
    """When UBERONBodyPartName is empty and SampleType is the source,
    the normaliser still runs."""
    from indicium_adapters_metabolomics import _matrix_normalizer

    monkeypatch.setattr(_matrix_normalizer, "normalize_matrix",
                        lambda text: ("leaf", "PO:0009025", 0.9))
    sample = {"SampleType": "dried foliage"}
    claims = redu_sample_to_claims(sample, "study:s1", normalize_matrix=True)
    matrix = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert matrix["ontology_terms"]["object"] == "PO:0009025"


# --- [ml]-gated tests (real model) ----------------------------------------

@ml_only
def test_real_model_normalizes_common_biofluid_aliases(tmp_path):
    """Smoke: MiniLM should map 'stool' → UBERON:0001988 (feces).

    Uses tmp_path as cache_dir so the test is hermetic and the embedding
    cache file gets created (exercises that branch)."""
    n = MatrixNormalizer(cache_dir=tmp_path, threshold=0.4)
    out = n.normalize("stool")
    assert out is not None
    label, curie, score = out
    assert curie == "UBERON:0001988"
    assert label == "feces"
    assert score >= 0.4
    # Cache file was written.
    assert list(tmp_path.glob("*_uberon_embeddings_v1.npz"))


@ml_only
def test_real_model_rejects_unrelated_input(tmp_path):
    """An obviously-unrelated phrase should fall below threshold."""
    n = MatrixNormalizer(cache_dir=tmp_path, threshold=DEFAULT_THRESHOLD)
    out = n.normalize("supersonic jet engine compressor blade")
    assert out is None


@ml_only
def test_real_model_uses_embeddings_cache(tmp_path):
    """Second-pass embedding load must not re-encode."""
    n1 = MatrixNormalizer(cache_dir=tmp_path, threshold=0.4)
    n1.normalize("urine")  # populates the cache
    cache_files = list(tmp_path.glob("*_uberon_embeddings_v1.npz"))
    assert cache_files
    mtime = cache_files[0].stat().st_mtime

    n2 = MatrixNormalizer(cache_dir=tmp_path, threshold=0.4)
    n2.normalize("blood plasma")
    # Cache file unchanged — same digest, same model.
    assert cache_files[0].stat().st_mtime == mtime
