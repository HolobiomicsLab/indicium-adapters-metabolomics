"""ReDU per-MSV metadata → asb:Claim projection.

Backend: GitHub-hosted snapshot at
`Wang-Bioinformatics-Lab/ReDU_metadata/main/metadata/<MSV>.tsv`.

We use the GH-hosted TSVs rather than the live `redu.ucsd.edu/filename`
endpoint because:

* The live ReDU endpoint was returning 503 at the time of writing — fragile.
* GH-hosted TSVs are versioned, mirrored, always up, and per-dataset (one
  file per MassIVE accession), so a single fetch caches metadata for every
  scan in a study — the lookup-per-file pattern collapses to one HTTP call
  per MSV.
* The schema is exactly what `redu_sample_to_claims` was already built for
  (MassiveID, filename, SampleType, SampleTypeSub1, NCBITaxonomy,
  UBERONBodyPartName, BiologicalSex, AgeInYears, DOIDCommonName,
  HealthStatus). PrUL-prefixed CURIE forms are normalised in the helper.

Public surface:
    redu_lookup(filename_or_path, *, session=None, cache_dir=...) -> dict | None
        Returns the per-file metadata row from the GH TSV, or None.
    redu_to_claims(filename, study_id, *, source_doi=None, sample_info=None)
                                                              -> list[Claim]
    redu_sample_to_claims(sample_info, subject, *, source_doi=None)
        Pure projection — no I/O. Used directly when the caller already
        has a row dict.

The `redu_sample_to_claims` projection maps:

| Source field                     | Qualifier              | Object form              |
|----------------------------------|------------------------|--------------------------|
| NCBITaxonomy (e.g. "9606|Homo")  | found_in_organism      | NCBITaxon:<id> CURIE     |
| UBERONBodyPartName               | acquired_from_matrix   | literal (UBERON CURIE if present) |
| SampleType / SampleTypeSub1      | acquired_from_matrix   | literal (fallback)       |
| DOIDCommonName                   | is_biomarker_for       | DOID:<id> CURIE          |
| MassSpectrometer                 | analyzed_with          | literal                  |
| IonizationSourceAndPolarity      | acquired_in_mode       | literal                  |
| ChromatographyAndPhase           | chromatographed_on     | literal                  |

The TSV schema only carries the first three groups. The MS-operational
columns (MassSpectrometer, etc.) come from the GNPS2 datasetcache datasette
which lives in `indicium_adapters_metabolomics.gnps.datasetcache` — the
same projection helper handles either source by tolerantly `.get()`-ing
every field.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

import requests

# Pin to `main` for now. If a tagged ReDU_metadata release ever appears,
# bump this to a tag.
REDU_GH_TSV_URL = (
    "https://raw.githubusercontent.com/Wang-Bioinformatics-Lab/"
    "ReDU_metadata/main/metadata/{msv}.tsv"
)

# GitHub Contents API for listing the per-MSV TSVs available in the snapshot.
REDU_GH_LIST_URL = (
    "https://api.github.com/repos/Wang-Bioinformatics-Lab/"
    "ReDU_metadata/contents/metadata?ref=main"
)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "indicium-adapters-metabolomics" / "redu"
USER_AGENT = (
    "indicium-adapters-metabolomics/0.6.0 redu "
    "(https://github.com/HolobiomicsLab/indicium-adapters-metabolomics)"
)

# Empty / sentinel cell values ReDU uses interchangeably with the empty string.
_EMPTY_SENTINELS = frozenset({"", "n/a", "na", "none", "null", "missing",
                              "ml.nofile", "not collected", "not applicable"})

# Matches `f.MSV000082048/...` or bare `MSV000082048/...` — extracts the MSV.
_MSV_RE = re.compile(r"^(?:f\.)?(?P<msv>MSV\d{9})(?:/(?P<rest>.*))?$")


def _msv_and_relpath(filename: str) -> tuple[str | None, str | None]:
    """Split a ReDU-style file query into (MSV accession, file basename).

    `f.MSV000082048/ccms_peak/Plate_28/30_84.mzML` → ('MSV000082048', '30_84.mzML')
    `MSV000082048/30_84.mzML`                       → ('MSV000082048', '30_84.mzML')
    `30_84.mzML` alone                              → (None, '30_84.mzML')
    """
    s = (filename or "").strip()
    if not s:
        return None, None
    m = _MSV_RE.match(s)
    if not m:
        # Bare filename — caller didn't include the MSV. Can't look up.
        return None, s.rsplit("/", 1)[-1] or None
    rest = m.group("rest") or ""
    return m.group("msv"), (rest.rsplit("/", 1)[-1] or None)


def _cache_path(msv: str, cache_dir: Path) -> Path:
    """Per-MSV TSV cache. Filenames are MSV-style so the cache dir is
    inspectable by humans (unlike a hash)."""
    return cache_dir / f"{msv}.tsv"


def _fetch_msv_tsv(
    msv: str,
    *,
    session: requests.Session | None,
    cache_dir: Path | None,
    timeout: float = 15.0,
) -> str | None:
    """Return raw TSV text for a single MSV accession. None on 404 / failure."""
    cache_path: Path | None = None
    if cache_dir is not None:
        cache_path = _cache_path(msv, cache_dir)
        if cache_path.exists():
            try:
                return cache_path.read_text(encoding="utf-8")
            except OSError:
                pass

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", USER_AGENT)
    try:
        r = sess.get(REDU_GH_TSV_URL.format(msv=msv), timeout=timeout)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    text = r.text

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
    return text


def _row_for_filename(tsv_text: str, filename_basename: str | None) -> dict[str, Any] | None:
    """Find the TSV row whose `filename` column matches `filename_basename`.

    If `filename_basename` is None or no row matches, returns the first row
    when there's only one row in the TSV (single-file datasets are common)
    or None otherwise."""
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    rows = list(reader)
    if not rows:
        return None
    if filename_basename:
        target = filename_basename.strip().lower()
        for row in rows:
            if (row.get("filename") or "").strip().lower() == target:
                return row
        return None
    return rows[0] if len(rows) == 1 else None


def redu_lookup(
    filename: str,
    *,
    session: requests.Session | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
    timeout: float = 15.0,
) -> dict[str, Any] | None:
    """Fetch the ReDU sample-metadata row for a MassIVE file path.

    `filename` follows the original ReDU `/filename?query=` shape —
    `f.MSV000082048/ccms_peak/Plate_28/30_84.mzML` or any path whose first
    segment is an MSV accession. The per-MSV TSV from
    `Wang-Bioinformatics-Lab/ReDU_metadata` is fetched and cached on disk;
    subsequent lookups in the same MSV are pure-Python (no network).

    Returns None on 404 (MSV not in the metadata snapshot), network
    failure, or no matching filename row in the TSV.

    Snapshot coverage caveat
    ------------------------
    The GH snapshot is curated and partial — at the time of writing it
    holds ~292 MSV deposits, biased toward older studies (MSV0000797xx
    through ~MSV000088xxx are well-represented; many newer MSVs are not).
    Use :func:`list_redu_msvs` to check coverage up front, or fall back to
    :mod:`indicium_adapters_metabolomics.gnps.datasetcache` for MS-
    operational metadata (instrument, mass analyzer, ionisation) when ReDU
    misses — datasetcache covers the full public MassIVE catalogue but
    lacks the biological sample metadata.
    """
    msv, basename = _msv_and_relpath(filename)
    if not msv:
        return None
    tsv_text = _fetch_msv_tsv(
        msv,
        session=session,
        cache_dir=Path(cache_dir) if cache_dir is not None else None,
        timeout=timeout,
    )
    if not tsv_text:
        return None
    return _row_for_filename(tsv_text, basename)


def list_redu_msvs(
    *,
    session: requests.Session | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
    timeout: float = 15.0,
) -> list[str] | None:
    """Return the sorted list of MSV accessions present in the GH snapshot.

    Hits the GitHub Contents API once, caches the result to
    `<cache_dir>/_msv_listing.json`. Returns None on network failure.

    Useful before bulk runs to skip MSVs that are known to be missing from
    the snapshot (saves one 404 per file). Example:

        known = set(list_redu_msvs() or ())
        for fp in filepaths:
            msv = fp.split('/')[0].removeprefix('f.')
            if msv in known:
                row = redu_lookup(fp)
                ...
    """
    import json as _json

    cache_path: Path | None = None
    if cache_dir is not None:
        cache_path = Path(cache_dir) / "_msv_listing.json"
        if cache_path.exists():
            try:
                return _json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", USER_AGENT)
    try:
        r = sess.get(REDU_GH_LIST_URL, timeout=timeout)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        items = r.json()
    except ValueError:
        return None
    msvs = sorted(
        item["name"].removesuffix(".tsv")
        for item in items
        if isinstance(item, dict)
        and item.get("type") == "file"
        and (item.get("name") or "").endswith(".tsv")
    )
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(_json.dumps(msvs, indent=2), encoding="utf-8")
    return msvs


def _clean(v: Any) -> str | None:
    """Strip whitespace + ReDU sentinel values. Returns None when effectively empty."""
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in _EMPTY_SENTINELS:
        return None
    return s


# CURIE / PURL normaliser. ReDU's NCBITaxonomy column is typically
# "<id>|<label>" (e.g. "9606|Homo sapiens"); we strip the label.
_PURL_RE = re.compile(r".*?/(?P<prefix>[A-Za-z]+)_(?P<lid>[0-9A-Za-z]+)$")


def _split_pipe_id(value: str | None) -> str | None:
    """ReDU uses `<id>|<label>` notation for taxonomic IDs."""
    if value is None:
        return None
    return value.split("|", 1)[0].strip() or None


def _to_curie(value: str | None, prefix: str) -> str | None:
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    if ":" in s and not s.startswith(("http://", "https://")):
        return s
    m = _PURL_RE.match(s)
    if m:
        return f"{m.group('prefix')}:{m.group('lid')}"
    if re.match(r"^[0-9A-Za-z]+$", s):
        return f"{prefix}:{s}"
    return None


def _claim(subject: str, qualifier: str, obj: str, *,
           ontology_term: str | None = None,
           source: str = "redu",
           source_doi: str | None = None) -> dict[str, Any]:
    c: dict[str, Any] = {
        "subject": subject, "qualifier": qualifier, "object": obj,
        "source": source,
    }
    if ontology_term is not None:
        c["ontology_terms"] = {"object": ontology_term}
        # The CURIE is resolved from a curated lookup column (NCBITaxonomy pipe-
        # delimited ID, UBERONOntologyIndex, DOIDOntologyIndex) — a curated
        # identifier resolution, not a free-text name match.
        c["ontology_term_justifications"] = {"object": "semapv:CompositeMatching"}
    if source_doi is not None:
        c["source_doi"] = source_doi
    return c


def _maybe_enrich_matrix(claim: dict[str, Any], text: str, *,
                         normalize_matrix: bool) -> None:
    """v0.7.0: in-place attach a UBERON / PO CURIE + score when MiniLM is on.

    Silent no-op when `normalize_matrix=False` or the [ml] extra is missing.
    Never raises — a model load failure just leaves the claim unchanged.
    """
    if not normalize_matrix or not text:
        return
    try:
        from indicium_adapters_metabolomics._matrix_normalizer import normalize_matrix as _norm
    except ImportError:  # pragma: no cover - import guard for partial installs
        return
    try:
        match = _norm(text)
    except Exception:  # pragma: no cover - never break the projection pipeline
        return
    if not match:
        return
    _label, curie, score = match
    claim.setdefault("ontology_terms", {})["object"] = curie
    claim.setdefault("evidence", {})["matrix_match_score"] = round(score, 4)
    # MiniLM cosine match against a curated seed list — a string/name (lexical) match.
    claim.setdefault("ontology_term_justifications", {})["object"] = (
        "semapv:LexicalMatching"
    )


def redu_sample_to_claims(
    sample_info: dict[str, Any],
    subject: str,
    *,
    source_doi: str | None = None,
    normalize_matrix: bool = False,
) -> list[dict[str, Any]]:
    """Project a single ReDU sample-metadata row to a list of claims.

    Pure function. Empty / sentinel fields produce no claim. Order is stable
    (organism → matrix → disease → ms → ionisation → chromatography). Works
    transparently against both the GH-TSV row schema (MassiveID, NCBITaxonomy,
    UBERONBodyPartName, …) and the live ReDU /filename JSON schema
    (ATTRIBUTE_NCBITaxonomy, ATTRIBUTE_Curated_BodyPartOntologyName, …).

    Parameters
    ----------
    normalize_matrix
        v0.7.0. When True and the optional ``[ml]`` extra is installed,
        free-text matrix labels lacking a UBERON CURIE are run through
        :mod:`indicium_adapters_metabolomics._matrix_normalizer` (MiniLM
        cosine match against a curated UBERON / PO seed list). On a
        confident hit (score ≥ threshold), the resolved CURIE is attached
        to the matrix claim's ``ontology_terms.object`` and the match
        score lands in ``evidence['matrix_match_score']``. The literal
        object string is preserved for traceability.

        Default False — preserves deterministic v0.6.x behavior. The
        flag is silently a no-op when the [ml] extra is missing, so
        opt-in code paths don't have to guard themselves.
    """
    claims: list[dict[str, Any]] = []

    # 1. Organism (NCBITaxon)
    taxon_id = (
        _clean(_split_pipe_id(sample_info.get("NCBITaxonomy")))
        or _clean(_split_pipe_id(sample_info.get("ATTRIBUTE_NCBITaxonomy")))
    )
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
            claim = _claim(subject, "acquired_from_matrix", uberon,
                           source_doi=source_doi)
            _maybe_enrich_matrix(claim, uberon, normalize_matrix=normalize_matrix)
            claims.append(claim)
    else:
        sample_type = _clean(sample_info.get("SampleTypeSub1")) \
            or _clean(sample_info.get("SampleType"))
        if sample_type:
            claim = _claim(subject, "acquired_from_matrix", sample_type,
                           source_doi=source_doi)
            _maybe_enrich_matrix(claim, sample_type, normalize_matrix=normalize_matrix)
            claims.append(claim)

    # 3. Disease (DOID)
    disease_name = _clean(sample_info.get("DOIDCommonName")) \
        or _clean(sample_info.get("ATTRIBUTE_DiseaseCommonName"))
    disease_id = _clean(sample_info.get("DOIDOntologyIndex")) \
        or _clean(sample_info.get("ATTRIBUTE_DiseaseOntology"))
    if disease_name:
        curie = _to_curie(disease_id, "DOID") if disease_id else None
        claims.append(_claim(subject, "is_biomarker_for", disease_name,
                             ontology_term=curie, source_doi=source_doi))

    # 4. Mass spectrometer (NOT in GH TSV schema; lives in datasetcache)
    ms = _clean(sample_info.get("MassSpectrometer"))
    if ms:
        claims.append(_claim(subject, "analyzed_with", ms,
                             source_doi=source_doi))

    # 5. Ionisation source + polarity
    ion = _clean(sample_info.get("IonizationSourceAndPolarity"))
    if ion:
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
    normalize_matrix: bool = False,
) -> list[dict[str, Any]]:
    """Fetch ReDU for `filename` and project to claims.

    Pass `sample_info=<dict>` to skip the HTTP call (offline tests,
    pre-fetched data). Otherwise `redu_lookup` is called with the same
    cache_dir / session knobs.

    `normalize_matrix=True` opts into the MiniLM matrix-name fallback
    (see :func:`redu_sample_to_claims`)."""
    if sample_info is None:
        sample_info = redu_lookup(filename, session=session, cache_dir=cache_dir)
    if not sample_info:
        return []
    return redu_sample_to_claims(sample_info, study_id, source_doi=source_doi,
                                 normalize_matrix=normalize_matrix)
