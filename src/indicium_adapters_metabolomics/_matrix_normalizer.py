"""MiniLM matrix-name fuzzy normaliser — v0.7.0.

Maps a free-text biological-matrix label (`"stool"`, `"blood plasma"`,
`"leaves"`) onto the closest UBERON / PO term from the curated seed list
in :file:`data/_uberon_terms.json`, returning the CURIE plus a similarity
score. Designed to be wired into :func:`redu_sample_to_claims` as a
fallback when ReDU's row carries no `UBERONOntologyIndex`.

Gated on the optional ``[ml]`` install extra
(`sentence-transformers` + `numpy`). On a fresh install without ``[ml]``,
:class:`MatrixNormalizer.available` is False and :func:`normalize_matrix`
returns None for every input — callers transparently skip the
enrichment.

Why bother
==========
ReDU's curated `UBERONBodyPartName` column is high-quality but sparse:
many deposits leave `BodyPartOntologyIndex` empty and only fill the
human-typed `SampleType` field with strings like "feces", "stool", or
"leaves". A small (~400KB on disk, ~50 MB in RAM at first call) sentence
transformer collapses that lexical noise to a deterministic CURIE
without us hand-curating every spelling variant.

Determinism
===========
The CURIE returned for a given input is fully determined by
(model_id, bundled `_uberon_terms.json`, threshold). The model weights
are pinned by `MODEL_NAME` and cached under
``~/.cache/indicium-adapters-metabolomics/ml/<model>``; the term
embeddings are computed once on first use and cached to
``<cache>/uberon_embeddings_v1.npz`` so subsequent process starts are
instant.
"""
from __future__ import annotations

import hashlib
import json
import warnings
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "indicium-adapters-metabolomics" / "ml"
DEFAULT_THRESHOLD = 0.55  # cosine; below this we return None
_EMBEDDINGS_CACHE_NAME = "uberon_embeddings_v1.npz"


def _load_uberon_terms() -> list[dict[str, Any]]:
    """Return the curated UBERON / PO term list (drops `_meta` etc.)."""
    path = files("indicium_adapters_metabolomics.data").joinpath("_uberon_terms.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [t for t in data.get("terms", []) if isinstance(t, dict) and "curie" in t]


def _term_phrases(term: dict[str, Any]) -> list[str]:
    """Phrases to encode for one UBERON term: label + every synonym."""
    out = [term["label"]]
    out.extend(s for s in (term.get("synonyms") or []) if s)
    return out


class MatrixNormalizer:
    """Lazy sentence-transformer matcher over the bundled UBERON terms.

    Constructor is cheap (no model load). The first :meth:`normalize` call
    triggers model download (cached on disk by HuggingFace) + corpus
    embedding (cached locally). Subsequent calls are pure-Python +
    numpy dot product over a (~70 × 384) matrix — sub-millisecond.

    Attributes
    ----------
    available : bool
        True iff `sentence-transformers` is importable. Tests can pivot
        on this to skip when the extra isn't installed.
    threshold : float
        Cosine-similarity floor below which :meth:`normalize` returns
        None. Default 0.55 — calibrated against the seed list so that
        completely unrelated text ("aircraft", "the year 1995") fails
        but typo-level drift ("blod plasma", "fece") succeeds.
    cache_dir : Path
        Embedding cache location. Override for tests.
    """

    def __init__(
        self,
        *,
        threshold: float = DEFAULT_THRESHOLD,
        cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
        model_name: str = MODEL_NAME,
    ):
        self.threshold = float(threshold)
        self.model_name = model_name
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self._model: Any | None = None
        self._terms: list[dict[str, Any]] | None = None
        self._embeddings: Any | None = None
        self._phrase_to_term_idx: list[int] | None = None

    @property
    def available(self) -> bool:
        try:
            import numpy  # noqa: F401
            import sentence_transformers  # noqa: F401
        except ImportError:
            return False
        return True

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        # Route HF cache under our own dir so a uniform `rm -rf cache_dir`
        # cleans everything. Falls back to HF default if cache_dir is None.
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = SentenceTransformer(self.model_name,
                                              cache_folder=str(self.cache_dir))
        else:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _load_terms_and_embeddings(self) -> None:
        if self._embeddings is not None:
            return
        import numpy as np

        self._terms = _load_uberon_terms()
        phrases: list[str] = []
        phrase_to_term_idx: list[int] = []
        for i, term in enumerate(self._terms):
            for phrase in _term_phrases(term):
                phrases.append(phrase)
                phrase_to_term_idx.append(i)
        self._phrase_to_term_idx = phrase_to_term_idx

        # Cache key includes phrase list digest so a JSON edit invalidates the
        # cache automatically.
        key = hashlib.sha1(
            "\x00".join(phrases).encode("utf-8") + self.model_name.encode("utf-8")
        ).hexdigest()[:16]
        cache_path = (self.cache_dir / f"{key}_{_EMBEDDINGS_CACHE_NAME}"
                      if self.cache_dir is not None else None)

        if cache_path is not None and cache_path.exists():
            try:
                with np.load(cache_path) as data:
                    cached = data["emb"].astype(np.float32, copy=False)
                # Scrub on load too — defends against cache files written by
                # an older build before nan_to_num was added.
                self._embeddings = np.nan_to_num(cached, nan=0.0,
                                                 posinf=0.0, neginf=0.0)
                return
            except (OSError, ValueError, KeyError):
                pass  # fall through and re-encode

        model = self._load_model()
        embeddings = model.encode(phrases, normalize_embeddings=True,
                                  show_progress_bar=False,
                                  convert_to_numpy=True)
        embeddings = np.asarray(embeddings, dtype=np.float32)
        # Defensive: some sentence-transformer backends (notably MPS on
        # Apple Silicon) can emit NaN values for short / single-token inputs
        # when normalize_embeddings=True divides by a near-zero norm. Replace
        # those with zero rows — they'll never win the argmax against a real
        # phrase and a sub-threshold score will be returned cleanly.
        embeddings = np.nan_to_num(embeddings, nan=0.0, posinf=0.0, neginf=0.0)
        self._embeddings = embeddings
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cache_path, emb=embeddings)

    def normalize(self, text: str) -> tuple[str, str, float] | None:
        """Return ``(label, curie, score)`` for the best UBERON / PO match.

        Returns None when the [ml] extra is not installed, the input is
        empty, or no term clears :attr:`threshold`.
        """
        if not text or not text.strip():
            return None
        if not self.available:
            return None
        import numpy as np

        self._load_terms_and_embeddings()
        assert self._embeddings is not None
        assert self._terms is not None
        assert self._phrase_to_term_idx is not None

        model = self._load_model()
        query = model.encode([text.strip()], normalize_embeddings=True,
                             show_progress_bar=False,
                             convert_to_numpy=True)
        query = np.asarray(query, dtype=np.float32)[0]
        query = np.nan_to_num(query, nan=0.0, posinf=0.0, neginf=0.0)
        # Suppress numpy "invalid value in matmul" warnings — they can fire
        # when MPS / single-token inputs produce a near-zero embedding, even
        # after nan_to_num. The semantics are still safe: a NaN row scores
        # below threshold and `normalize()` returns None.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning,
                                    message=".*matmul.*")
            sims = self._embeddings @ query  # cosine; both sides are unit-norm
        best_phrase_idx = int(np.argmax(sims))
        score = float(sims[best_phrase_idx])
        if score < self.threshold:
            return None
        term = self._terms[self._phrase_to_term_idx[best_phrase_idx]]
        return term["label"], term["curie"], score


# Module-level singleton — lazy across the whole process.
MATRIX_NORMALIZER = MatrixNormalizer()


def normalize_matrix(text: str) -> tuple[str, str, float] | None:
    """Convenience wrapper around the module singleton."""
    return MATRIX_NORMALIZER.normalize(text)
