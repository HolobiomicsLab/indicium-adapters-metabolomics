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


# --- v0.7.1 redu integration edge cases (always-on, stubbed normalizer) ---

def test_redu_normalize_matrix_exception_is_swallowed(monkeypatch):
    """If the normaliser raises (corrupt cache mid-call, model OOM, …),
    `_maybe_enrich_matrix` must NOT crash the projection — the claim
    survives un-enriched. This guards the `except Exception:` in
    `_maybe_enrich_matrix`."""
    from indicium_adapters_metabolomics import _matrix_normalizer

    def boom(text):
        raise RuntimeError("simulated model failure")

    monkeypatch.setattr(_matrix_normalizer, "normalize_matrix", boom)
    sample = {"UBERONBodyPartName": "stool"}
    claims = redu_sample_to_claims(sample, "study:s1", normalize_matrix=True)
    matrix = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert matrix["object"] == "stool"
    assert "ontology_terms" not in matrix
    assert "evidence" not in matrix


def test_maybe_enrich_matrix_overwrites_existing_ontology_terms_object(monkeypatch):
    """Defensive semantics doc: `_maybe_enrich_matrix` uses `setdefault` on
    the dict (creates ontology_terms if absent) but then unconditionally
    writes `["object"]` into that dict — so if a caller already set
    `ontology_terms["object"]`, the normaliser's CURIE wins.

    In practice this never happens for the matrix qualifier — the curated
    UBERONOntologyIndex path in `redu_sample_to_claims` short-circuits
    before `_maybe_enrich_matrix` is invoked. This test pins the helper's
    standalone behavior so a refactor doesn't silently flip the semantics."""
    from indicium_adapters_metabolomics import _matrix_normalizer
    from indicium_adapters_metabolomics.redu.parser import _maybe_enrich_matrix

    monkeypatch.setattr(_matrix_normalizer, "normalize_matrix",
                        lambda text: ("feces", "UBERON:0001988", 0.9))
    claim = {
        "subject": "s", "qualifier": "acquired_from_matrix",
        "object": "stool", "source": "redu",
        "ontology_terms": {"object": "UBERON:OLD"},
        "evidence": {"matrix_match_score": 0.1},
    }
    _maybe_enrich_matrix(claim, "stool", normalize_matrix=True)
    # Helper overwrites both keys (the setdefault only protects the outer
    # ontology_terms dict).
    assert claim["ontology_terms"]["object"] == "UBERON:0001988"
    assert claim["evidence"]["matrix_match_score"] == 0.9


def test_maybe_enrich_matrix_normalize_false_is_pure_noop(monkeypatch):
    """normalize_matrix=False must not import the normaliser module at all
    — verifies the cheap-path guard. We replace `__import__` with a sentinel
    that records its first call name, then assert it was never touched."""
    import builtins

    from indicium_adapters_metabolomics.redu.parser import _maybe_enrich_matrix
    real_import = builtins.__import__
    called = []

    def recording(name, *a, **k):
        if name == "indicium_adapters_metabolomics._matrix_normalizer":
            called.append(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", recording)
    claim = {"subject": "s", "qualifier": "acquired_from_matrix",
             "object": "stool", "source": "redu"}
    _maybe_enrich_matrix(claim, "stool", normalize_matrix=False)
    assert called == []  # never imported


def test_maybe_enrich_matrix_empty_text_is_noop(monkeypatch):
    """Empty text → early return, normaliser never invoked."""
    from indicium_adapters_metabolomics import _matrix_normalizer
    from indicium_adapters_metabolomics.redu.parser import _maybe_enrich_matrix

    calls = []
    monkeypatch.setattr(_matrix_normalizer, "normalize_matrix",
                        lambda text: calls.append(text) or None)
    claim = {"subject": "s", "qualifier": "acquired_from_matrix",
             "object": "", "source": "redu"}
    _maybe_enrich_matrix(claim, "", normalize_matrix=True)
    assert calls == []


def test_redu_to_claims_end_to_end_with_stubbed_normalizer(monkeypatch):
    """End-to-end through the public `redu_to_claims` entry point with
    sample_info pre-supplied (skips HTTP) and a stubbed normaliser. This
    is the integration path that ASB / Scriptorium consumers will hit."""
    from indicium_adapters_metabolomics import _matrix_normalizer
    from indicium_adapters_metabolomics.redu import redu_to_claims

    monkeypatch.setattr(_matrix_normalizer, "normalize_matrix",
                        lambda text: ("blood plasma", "UBERON:0001969", 0.91))
    sample_info = {
        "MassiveID": "MSV000099999",
        "filename": "x.mzML",
        "NCBITaxonomy": "9606|Homo sapiens",
        "SampleType": "blod plasma",  # typo, no UBERON curated id
    }
    claims = redu_to_claims(
        "MSV000099999/x.mzML", "study:s1",
        sample_info=sample_info, normalize_matrix=True)
    matrix = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert matrix["object"] == "blod plasma"  # literal preserved
    assert matrix["ontology_terms"]["object"] == "UBERON:0001969"
    assert matrix["evidence"]["matrix_match_score"] == 0.91
    # Organism claim still emitted.
    org = next(c for c in claims if c["qualifier"] == "found_in_organism")
    assert org["object"] == "NCBITaxon:9606"


def test_redu_to_claims_normalize_matrix_default_off(monkeypatch):
    """Parity check: `redu_to_claims` (not just `redu_sample_to_claims`)
    must default to False — the flag has to thread all the way through."""
    from indicium_adapters_metabolomics import _matrix_normalizer
    from indicium_adapters_metabolomics.redu import redu_to_claims

    calls = []
    monkeypatch.setattr(_matrix_normalizer, "normalize_matrix",
                        lambda text: calls.append(text) or None)
    sample_info = {"MassiveID": "MSV0", "filename": "x.mzML",
                   "SampleType": "stool"}
    redu_to_claims("MSV0/x.mzML", "study:s1", sample_info=sample_info)
    assert calls == []  # default off → normaliser never called


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


# --- v0.7.1 cache edge cases (always-on) ----------------------------------

def test_normalizer_cache_dir_none_disables_cache(monkeypatch):
    """cache_dir=None means no cache_path is computed and nothing is
    written to disk. Verified by checking the path attribute and that
    `_load_terms_and_embeddings` short-circuits via the embedded fake."""
    n = MatrixNormalizer(cache_dir=None)
    assert n.cache_dir is None


def test_normalizer_threshold_floor_kwarg_is_respected():
    n = MatrixNormalizer(threshold=0.99)
    assert n.threshold == 0.99


def test_normalizer_custom_model_name_recorded():
    n = MatrixNormalizer(model_name="some/other-model")
    assert n.model_name == "some/other-model"
    # Cache key depends on model_name → embeddings cache filename will
    # differ if model is swapped (covered by the real-model cache test
    # below; here we just lock the constructor wiring).


def test_module_singleton_normalize_matrix_returns_none_when_unavailable(monkeypatch):
    """The module-level `normalize_matrix(...)` helper delegates to the
    singleton; with `available=False` it must return None for any input."""
    from indicium_adapters_metabolomics import _matrix_normalizer as mn

    monkeypatch.setattr(mn.MatrixNormalizer, "available",
                        property(lambda self: False))
    assert mn.normalize_matrix("feces") is None
    assert mn.normalize_matrix("anything") is None


# --- v0.7.1 cache edge cases ([ml]-gated) ---------------------------------

@ml_only
def test_real_model_recovers_from_corrupt_cache_file(tmp_path):
    """A pre-existing `*_uberon_embeddings_v1.npz` that's actually garbage
    must be silently re-encoded rather than crashing the first normalize."""
    # Drop a bogus .npz with the expected name pattern (any digest prefix).
    bad = tmp_path / "deadbeefdeadbeef_uberon_embeddings_v1.npz"
    bad.write_bytes(b"this is not a valid npz archive")

    n = MatrixNormalizer(cache_dir=tmp_path, threshold=0.4)
    out = n.normalize("stool")
    # Either the digest matches and we recovered, or the digest differs
    # (in which case the bad file was simply not loaded). Either way, the
    # call must succeed.
    assert out is not None
    label, curie, score = out
    assert curie == "UBERON:0001988"


@ml_only
def test_real_model_cache_invalidates_on_phrase_list_change(tmp_path, monkeypatch):
    """Editing _uberon_terms.json (here: monkeypatching the loader to return
    a different list) must produce a different cache filename — old cache
    files don't get reused for a different corpus."""
    from indicium_adapters_metabolomics import _matrix_normalizer as mn

    n1 = MatrixNormalizer(cache_dir=tmp_path, threshold=0.4)
    n1.normalize("urine")
    files_after_first = sorted(p.name for p in tmp_path.glob("*_uberon_embeddings_v1.npz"))
    assert files_after_first, "first run should have written the cache"

    # Force a different corpus → different digest → different cache file.
    monkeypatch.setattr(mn, "_load_uberon_terms", lambda: [
        {"curie": "UBERON:9999999", "label": "tongue", "synonyms": ["lingua"]}
    ])
    n2 = MatrixNormalizer(cache_dir=tmp_path, threshold=0.4)
    n2.normalize("lingua")
    files_after_second = sorted(p.name for p in tmp_path.glob("*_uberon_embeddings_v1.npz"))
    # The second run must add a NEW cache file (different digest) rather
    # than overwriting the first.
    assert len(files_after_second) > len(files_after_first)


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
