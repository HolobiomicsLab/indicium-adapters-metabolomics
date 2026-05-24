"""GNPS2 datasetcache datasette → asb:Claim projection.

`https://datasetcache.gnps2.org/datasette/` exposes a SQLite mirror of the
public MassIVE catalogue as a Datasette JSON API. Two relevant tables:

* `filename`  — basic file metadata (size, sample_type, instrument_vendor,
                instrument_model, MS1/MS2 counts).
* `uniquemri` — same columns + auto-extracted MS-operational metadata
                (MassAnalyzer, Ionization, RT_Range_in_Min, Top_CEs,
                classification e.g. "DDA"/"DIA").

This complements `indicium_adapters_metabolomics.redu` (which carries the
biological sample metadata from `Wang-Bioinformatics-Lab/ReDU_metadata`).
ReDU is "what was sampled"; datasetcache is "how it was measured".

Projection mapping:

| uniquemri column       | Qualifier              | Object form               |
|------------------------|------------------------|---------------------------|
| MassAnalyzer           | uses_mass_analyzer     | semicolon-list literal    |
| Ionization             | acquired_in_mode       | semicolon-list literal    |
| instrument_model       | analyzed_with          | literal                   |
| instrument_vendor      | (folded into evidence) | -                         |
| sample_type            | acquired_from_matrix   | literal (last-resort)     |

Public surface:
    fetch_datasetcache_row(filepath, *, table="uniquemri", session=None,
                           cache_dir=...) -> dict | None
    datasetcache_row_to_claims(row, subject, *, source_doi=None)
        -> list[Claim]
    datasetcache_to_claims(filepath, study_id, *, row=None, ...) -> list[Claim]
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import requests

DATASETCACHE_BASE = "https://datasetcache.gnps2.org/datasette/database"
DEFAULT_CACHE_DIR = (
    Path.home() / ".cache" / "indicium-adapters-metabolomics" / "datasetcache"
)
USER_AGENT = (
    "indicium-adapters-metabolomics/0.6.0 gnps2-datasetcache "
    "(https://github.com/HolobiomicsLab/indicium-adapters-metabolomics)"
)

# Datasette tables we know about. Other tables (`filename`) are allowed via
# the `table` kwarg but uniquemri is the default since it carries the richest
# MS-operational columns.
_KNOWN_TABLES = frozenset({"uniquemri", "filename"})

# Sentinels datasetcache uses for "missing/unknown".
_EMPTY = frozenset({"", "nan", "n/a", "na", "none", "null", "unknown"})


def _clean(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in _EMPTY:
        return None
    return s


def _claim(subject: str, qualifier: str, obj: str, *,
           evidence: dict[str, Any] | None = None,
           source: str = "gnps2-datasetcache",
           source_doi: str | None = None) -> dict[str, Any]:
    c: dict[str, Any] = {
        "subject": subject, "qualifier": qualifier, "object": obj,
        "source": source,
    }
    if evidence:
        c["evidence"] = evidence
    if source_doi is not None:
        c["source_doi"] = source_doi
    return c


def _cache_path(filepath: str, table: str, cache_dir: Path) -> Path:
    h = hashlib.sha1(f"{table}\x00{filepath}".encode()).hexdigest()
    return cache_dir / f"{h}.json"


def fetch_datasetcache_row(
    filepath: str,
    *,
    table: str = "uniquemri",
    session: requests.Session | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
    timeout: float = 15.0,
) -> dict[str, Any] | None:
    """Look up one row by `filepath` from the datasetcache datasette.

    `filepath` is the dataset-relative path the datasette stores — e.g.
    `ccms_peak/Plate_22/11_12.mzML` (no leading slash, no `f.` prefix).
    Returns the row dict (objects-shape) or None on miss / failure.

    `table` defaults to `uniquemri` because it carries the MS-operational
    columns (MassAnalyzer, Ionization) we project; pass `table="filename"`
    for the lighter base catalogue if you only need size + sample_type.
    """
    if not filepath or not filepath.strip():
        return None
    if table not in _KNOWN_TABLES:
        return None

    cache_path: Path | None = None
    if cache_dir is not None:
        cache_path = _cache_path(filepath, table, Path(cache_dir))
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                # Cached miss sentinel is the literal {} — same as a "no row".
                return cached or None
            except (OSError, ValueError):
                pass

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", USER_AGENT)
    try:
        r = sess.get(
            f"{DATASETCACHE_BASE}/{table}.json",
            params={"filepath__exact": filepath, "_shape": "objects",
                    "_size": 1},
            timeout=timeout,
        )
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None

    rows = data.get("rows") or []
    # `_shape=objects` returns a list of dicts (not list-of-lists).
    row = rows[0] if rows and isinstance(rows[0], dict) else None

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(row or {}, indent=2), encoding="utf-8")
    return row


def datasetcache_row_to_claims(
    row: dict[str, Any],
    subject: str,
    *,
    source_doi: str | None = None,
) -> list[dict[str, Any]]:
    """Project a datasetcache row into the existing adapter qualifier vocab.

    Pure function. Stable ordering: instrument → mass-analyzer → ionisation
    → matrix.
    """
    claims: list[dict[str, Any]] = []
    if not row:
        return claims

    # 1. Instrument model + vendor → analyzed_with (vendor in evidence)
    model = _clean(row.get("instrument_model"))
    vendor = _clean(row.get("instrument_vendor"))
    if model:
        evidence: dict[str, Any] = {}
        if vendor:
            evidence["instrument_vendor"] = vendor
        claims.append(_claim(subject, "analyzed_with", model,
                             evidence=evidence or None,
                             source_doi=source_doi))

    # 2. Mass analyzer → uses_mass_analyzer
    mass_analyzer = _clean(row.get("MassAnalyzer"))
    if mass_analyzer:
        claims.append(_claim(subject, "uses_mass_analyzer", mass_analyzer,
                             source_doi=source_doi))

    # 3. Ionisation → acquired_in_mode
    ion = _clean(row.get("Ionization"))
    if ion:
        claims.append(_claim(subject, "acquired_in_mode", ion,
                             source_doi=source_doi))

    # 4. Matrix fallback. The `sample_type` column on datasetcache is
    # operational (e.g. "GNPS", "MASSIVE-KCF"), NOT biological — so we only
    # emit it if it looks like a real matrix word and there's no claim from
    # the (more authoritative) ReDU layer.
    sample_type = _clean(row.get("sample_type"))
    if sample_type and sample_type.lower() not in {"gnps", "massive",
                                                    "massive-kcf"}:
        claims.append(_claim(subject, "acquired_from_matrix", sample_type,
                             source_doi=source_doi))

    return claims


def datasetcache_to_claims(
    filepath: str,
    study_id: str,
    *,
    row: dict[str, Any] | None = None,
    source_doi: str | None = None,
    table: str = "uniquemri",
    session: requests.Session | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
) -> list[dict[str, Any]]:
    """Fetch a datasetcache row for `filepath` and project to claims.

    Pass `row=<dict>` to bypass the HTTP call. Subject of every emitted
    claim is `study_id` (typically the asb study/paper identifier)."""
    if row is None:
        row = fetch_datasetcache_row(filepath, table=table, session=session,
                                     cache_dir=cache_dir)
    if not row:
        return []
    return datasetcache_row_to_claims(row, study_id, source_doi=source_doi)
