"""ReDU `/filename` parser — per-file sample-metadata → asb:Claim projection.

Two entry points:

* `redu_lookup(filename, *, session=None, cache_dir=...)` — HTTP GET against
  the live ReDU endpoint with a content-addressed on-disk cache. Returns the
  decoded JSON dict, or None on 404 / 5xx / network failure. Caller decides
  whether to retry.
* `redu_to_claims(filename, study_id, *, source_doi=None, sample_info=None)` —
  convenience wrapper that calls `redu_lookup` (or accepts a pre-fetched
  `sample_info` dict for offline tests) and projects the response through
  `redu_sample_to_claims`.
* `redu_sample_to_claims(sample_info, subject, *, source_doi=None)` — pure
  projection from sample dict → list[Claim]. No I/O. Used directly when the
  caller already has ReDU JSON from a bulk dump.

Field mapping (closes audit-2 finding 6e tier-1):

| ReDU field                       | Qualifier              | Object form              |
|----------------------------------|------------------------|--------------------------|
| NCBITaxonomy                     | found_in_organism      | NCBITaxon:<id> CURIE     |
| UBERONBodyPartName               | acquired_from_matrix   | UBERON:<id> CURIE        |
| SampleType / SampleTypeSub1      | acquired_from_matrix   | literal (free-text)      |
| DOIDCommonName                   | is_biomarker_for       | DOID:<id> CURIE          |
| MassSpectrometer                 | analyzed_with          | literal                  |
| IonizationSourceAndPolarity      | acquired_in_mode       | literal (e.g. "positive")|
| ChromatographyAndPhase           | chromatographed_on     | literal                  |

ReDU sometimes ships pre-prefixed ontology IDs (e.g. `NCBITaxon:9606`) and
sometimes bare IDs (e.g. `9606`). The helpers normalise either form.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import requests

# The live endpoint shape the user supplied:
#   GET https://redu.ucsd.edu/filename?query=f.<MSV>/<path>/<file>.mzML
REDU_URL = "https://redu.ucsd.edu/filename"

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "indicium-adapters-metabolomics" / "redu"
USER_AGENT = (
    "indicium-adapters-metabolomics/0.6.0 redu "
    "(https://github.com/HolobiomicsLab/indicium-adapters-metabolomics)"
)

# ReDU "ml.nofile" / "missing" sentinels we should treat as no-data.
_EMPTY_SENTINELS = frozenset({"", "n/a", "na", "none", "null", "missing",
                              "ml.nofile", "not collected", "not applicable"})


def _cache_path(filename: str, cache_dir: Path) -> Path:
    """Content-address by SHA-1 of the query string; the raw filename has
    slashes that can't be filesystem keys."""
    key = hashlib.sha1(filename.encode("utf-8")).hexdigest()
    return cache_dir / f"{key}.json"


def redu_lookup(
    filename: str,
    *,
    session: requests.Session | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
    timeout: float = 15.0,
) -> dict[str, Any] | None:
    """Fetch the ReDU sample-metadata record for a MassIVE file path.

    `filename` is the same string the user passes to ReDU's `?query=` param —
    e.g. `f.MSV000082048/ccms_peak/Plate_28/30_84.mzML`.

    On success returns the decoded JSON dict. On 404 / 503 / network failure
    returns None — caller decides whether to retry. Cached to disk by SHA-1
    of the filename so re-runs are free; pass `cache_dir=None` to disable.
    """
    if not filename or not filename.strip():
        return None

    cache_path: Path | None = None
    if cache_dir is not None:
        cache_path = _cache_path(filename, Path(cache_dir))
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass  # corrupt cache; fall through to refetch

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", USER_AGENT)
    try:
        r = sess.get(REDU_URL, params={"query": filename}, timeout=timeout)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def _clean(v: Any) -> str | None:
    """Strip whitespace and ReDU sentinel values. Returns None if empty."""
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in _EMPTY_SENTINELS:
        return None
    return s


# Tolerant ontology-CURIE normaliser. ReDU sometimes ships pre-prefixed values
# ("NCBITaxon:9606"), sometimes bare IDs ("9606"), sometimes purl IRIs
# ("http://purl.obolibrary.org/obo/NCBITaxon_9606"). We accept all three and
# emit `<PREFIX>:<id>`.
_PURL_RE = re.compile(r".*?/(?P<prefix>[A-Za-z]+)_(?P<lid>[0-9A-Za-z]+)$")


def _to_curie(value: str | None, prefix: str) -> str | None:
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    # Already a CURIE?
    if ":" in s and not s.startswith(("http://", "https://")):
        return s
    # PURL?
    m = _PURL_RE.match(s)
    if m:
        return f"{m.group('prefix')}:{m.group('lid')}"
    # Bare local ID (digits or alphanumeric)
    if re.match(r"^[0-9A-Za-z]+$", s):
        return f"{prefix}:{s}"
    return None


def _claim(subject: str, qualifier: str, obj: str, *,
           ontology_term: str | None = None,
           source: str = "redu",
           source_doi: str | None = None) -> dict[str, Any]:
    """Build a minimally-populated asb:Claim dict in the shape the adapter
    family already round-trips. Evidence is stamped with the ReDU source so
    Scriptorium/Perspicacite-AI can dedupe across origin paths."""
    c: dict[str, Any] = {
        "subject": subject,
        "qualifier": qualifier,
        "object": obj,
        "source": source,
    }
    if ontology_term is not None:
        c["ontology_terms"] = {"object": ontology_term}
    if source_doi is not None:
        c["source_doi"] = source_doi
    return c


def redu_sample_to_claims(
    sample_info: dict[str, Any],
    subject: str,
    *,
    source_doi: str | None = None,
) -> list[dict[str, Any]]:
    """Project a single ReDU sample-metadata record to a list of claims.

    Pure function; no I/O. `subject` is the asb:Claim subject for every
    emitted claim (typically the study/capsule ID or paper DOI). Empty /
    sentinel fields produce no claim. Order of emitted claims is stable
    (organism → matrix → disease → ms → ionisation → chromatography) so
    diffing two ReDU responses is straightforward.
    """
    claims: list[dict[str, Any]] = []

    # 1. Organism (NCBITaxon)
    taxon_id = _clean(sample_info.get("NCBITaxonomy")) \
        or _clean(sample_info.get("ATTRIBUTE_NCBITaxonomy"))
    if taxon_id:
        curie = _to_curie(taxon_id, "NCBITaxon")
        if curie:
            claims.append(_claim(subject, "found_in_organism", curie,
                                 ontology_term=curie, source_doi=source_doi))

    # 2. Matrix (UBERON body part if present, otherwise free-text SampleType)
    uberon = _clean(sample_info.get("UBERONBodyPartName")) \
        or _clean(sample_info.get("ATTRIBUTE_Curated_BodyPartOntologyName"))
    uberon_id = _clean(sample_info.get("UBERONOntologyIndex")) \
        or _clean(sample_info.get("ATTRIBUTE_Curated_BodyPartOntologyIndex"))
    if uberon:
        if uberon_id:
            curie = _to_curie(uberon_id, "UBERON")
            claims.append(_claim(subject, "acquired_from_matrix", uberon,
                                 ontology_term=curie, source_doi=source_doi))
        else:
            claims.append(_claim(subject, "acquired_from_matrix", uberon,
                                 source_doi=source_doi))
    else:
        # Fall back to ReDU's free-text SampleType / SampleTypeSub1.
        sample_type = _clean(sample_info.get("SampleTypeSub1")) \
            or _clean(sample_info.get("SampleType"))
        if sample_type:
            claims.append(_claim(subject, "acquired_from_matrix", sample_type,
                                 source_doi=source_doi))

    # 3. Disease (DOID)
    disease_name = _clean(sample_info.get("DOIDCommonName")) \
        or _clean(sample_info.get("ATTRIBUTE_DiseaseCommonName"))
    disease_id = _clean(sample_info.get("DOIDOntologyIndex")) \
        or _clean(sample_info.get("ATTRIBUTE_DiseaseOntology"))
    if disease_name:
        curie = _to_curie(disease_id, "DOID") if disease_id else None
        c = _claim(subject, "is_biomarker_for", disease_name,
                   ontology_term=curie, source_doi=source_doi)
        claims.append(c)

    # 4. Mass spectrometer
    ms = _clean(sample_info.get("MassSpectrometer"))
    if ms:
        claims.append(_claim(subject, "analyzed_with", ms,
                             source_doi=source_doi))

    # 5. Ionisation source + polarity
    ion = _clean(sample_info.get("IonizationSourceAndPolarity"))
    if ion:
        # Common ReDU forms: "ESI positive", "ESI negative", "MALDI positive".
        # Project the polarity (positive/negative) to acquired_in_mode literal
        # but pass the full string through to keep the source info recoverable.
        claims.append(_claim(subject, "acquired_in_mode", ion,
                             source_doi=source_doi))

    # 6. Chromatography
    chrom = _clean(sample_info.get("ChromatographyAndPhase"))
    if chrom:
        claims.append(_claim(subject, "chromatographed_on", chrom,
                             source_doi=source_doi))

    return claims


def redu_to_claims(
    filename: str,
    study_id: str,
    *,
    source_doi: str | None = None,
    sample_info: dict[str, Any] | None = None,
    session: requests.Session | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
) -> list[dict[str, Any]]:
    """High-level convenience: fetch ReDU for `filename` and project to claims.

    Pass `sample_info=<dict>` to skip the HTTP call (useful for offline tests
    and for callers that already have ReDU JSON from a bulk dump). Otherwise
    `redu_lookup` is called with the same cache_dir / session knobs."""
    if sample_info is None:
        sample_info = redu_lookup(filename, session=session, cache_dir=cache_dir)
    if not sample_info:
        return []
    return redu_sample_to_claims(sample_info, study_id, source_doi=source_doi)
