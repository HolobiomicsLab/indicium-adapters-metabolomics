"""GNPS ProteoSAFe parsers — result_json + ManageParameters → asb:Claim.

Two pure-projection functions and their HTTP wrappers:

* `parse_gnps_annotations(blockdata, task_id, *, source_doi=None)` —
  consumes the `blockData` list from
  `result_json.jsp?view=view_all_annotations_DB`. Emits `spectral_match`
  claims (MetaboKGAdapter vocab) with MQScore + SharedPeaks evidence and
  the GNPS USI as ontology term.

* `parse_gnps_parameters(xml_text, task_id, *, source_doi=None)` —
  consumes the ManageParameters XML. Emits `has_processing_software`
  (workflow name, canonicalised through the v0.5.0 software registry),
  `analyzed_with` (tolerances), `acquired_in_mode` (ion mode).

HTTP layer (`fetch_*`) shares the same cache-on-disk + tolerant-failure
pattern as the ReDU module. Live calls require explicit cache_dir or
session; CI tests rely on the offline fixtures.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import requests

from indicium_adapters_metabolomics._registries import canonical_software_name

GNPS_RESULT_JSON_URL = "https://gnps.ucsd.edu/ProteoSAFe/result_json.jsp"
GNPS_PARAMETERS_URL = "https://gnps.ucsd.edu/ProteoSAFe/ManageParameters"

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "indicium-adapters-metabolomics" / "gnps"
USER_AGENT = (
    "indicium-adapters-metabolomics/0.6.0 gnps "
    "(https://github.com/HolobiomicsLab/indicium-adapters-metabolomics)"
)


# ----------- helpers -----------------------------------------------------

def _clean(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.upper() in {"N/A", "NA", "NONE", "NULL"}:
        return None
    return s


def _float_or_none(v: Any) -> float | None:
    s = _clean(v)
    if s is None:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _claim(subject: str, qualifier: str, obj: str, *,
           ontology_term: str | None = None,
           evidence: dict[str, Any] | None = None,
           source: str = "gnps",
           source_doi: str | None = None) -> dict[str, Any]:
    c: dict[str, Any] = {
        "subject": subject, "qualifier": qualifier, "object": obj,
        "source": source,
    }
    if ontology_term is not None:
        c["ontology_terms"] = {"object": ontology_term}
    if evidence:
        c["evidence"] = evidence
    if source_doi is not None:
        c["source_doi"] = source_doi
    return c


def _cache_path(key_parts: tuple[str, ...], cache_dir: Path) -> Path:
    h = hashlib.sha1("\x00".join(key_parts).encode("utf-8")).hexdigest()
    return cache_dir / f"{h}.json"


# ----------- annotations (result_json) -----------------------------------

def parse_gnps_annotations(
    blockdata: list[dict[str, Any]],
    task_id: str,
    *,
    source_doi: str | None = None,
) -> list[dict[str, Any]]:
    """Project `blockData` rows from `view_all_annotations_DB` to claims.

    Per-row mapping:
      subject = "gnps_task:<task_id>:scan:<#Scan#>"   (the cluster feature)
      qualifier = "spectral_match"  (MetaboKGAdapter vocab)
      object = Compound_Name
      ontology_terms.object = "mzspec:GNPS:<library>:accession:<SpectrumID>"
                              (USI when SpectrumID present)
      evidence = {mq_score, shared_peaks, mz_error_ppm, mass_diff, ion_mode,
                  precursor_mz, retention_time, library, library_quality}

    Rows with an empty Compound_Name are skipped — those are unannotated
    clusters that came through the view by accident.
    """
    out: list[dict[str, Any]] = []
    for row in blockdata or []:
        name = _clean(row.get("Compound_Name"))
        scan = _clean(row.get("#Scan#"))
        if not name or not scan:
            continue
        subject = f"gnps_task:{task_id}:scan:{scan}"
        spectrum_id = _clean(row.get("SpectrumID"))
        usi = (
            f"mzspec:GNPS:GNPS-LIBRARY:accession:{spectrum_id}"
            if spectrum_id else None
        )
        evidence = {
            "mq_score":       _float_or_none(row.get("MQScore")),
            "shared_peaks":   _float_or_none(row.get("SharedPeaks")),
            "mz_error_ppm":   _float_or_none(row.get("MZErrorPPM")),
            "mass_diff":      _float_or_none(row.get("MassDiff")),
            "precursor_mz":   _float_or_none(row.get("Precursor_MZ")),
            "retention_time": _float_or_none(row.get("RT_Query")),
            "ion_mode":       _clean(row.get("IonMode")),
            "adduct":         _clean(row.get("Adduct")),
            "library":        _clean(row.get("LibraryName")),
            "library_quality": _clean(row.get("LibraryQualityString")),
            "spectrum_id":    spectrum_id,
        }
        # Drop empty evidence values for compactness.
        evidence = {k: v for k, v in evidence.items() if v is not None}
        out.append(_claim(subject, "spectral_match", name,
                          ontology_term=usi,
                          evidence=evidence or None,
                          source_doi=source_doi))
    return out


def fetch_gnps_annotations(
    task_id: str,
    *,
    session: requests.Session | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
    timeout: float = 30.0,
) -> dict[str, Any] | None:
    """GET `result_json.jsp?task=<task_id>&view=view_all_annotations_DB`.

    Returns the decoded JSON object (with `blockData` list) or None on
    error. Cached to disk by task_id+view; pass cache_dir=None to disable.
    The endpoint replies with `text/html` content-type for JSON bodies —
    we json-parse the text directly instead of trusting `r.json()`.
    """
    if not task_id or not task_id.strip():
        return None
    view = "view_all_annotations_DB"
    cache_path: Path | None = None
    if cache_dir is not None:
        cache_path = _cache_path((task_id, view), Path(cache_dir))
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", USER_AGENT)
    try:
        r = sess.get(GNPS_RESULT_JSON_URL,
                     params={"task": task_id, "view": view},
                     timeout=timeout)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        data = json.loads(r.text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


# ----------- ManageParameters XML ----------------------------------------

# Subset of GNPS workflow IDs we know about; canonical_software_name() also
# resolves "GNPS"/"gnps"/"gnps2" → "GNPS", which is what we use here. Any
# unknown workflow ID falls back to the literal "GNPS (<workflow>)".
_GNPS_WORKFLOW_LABELS: dict[str, str] = {
    "METABOLOMICS-SNETS-V2":        "GNPS Classical Molecular Networking",
    "FEATURE-BASED-MOLECULAR-NETWORKING": "GNPS Feature-Based Molecular Networking",
    "MOLECULAR-LIBRARYSEARCH-V2":   "GNPS Library Search",
    "MASST-V2":                     "GNPS MASST",
}


def parse_gnps_parameters(
    xml_text: str,
    task_id: str,
    *,
    source_doi: str | None = None,
) -> list[dict[str, Any]]:
    """Project a ManageParameters XML document to study-level claims.

    Field → qualifier mapping:
      workflow             → has_processing_software (canonicalised)
      tolerance.PM_tolerance, tolerance.Ion_tolerance, MIN_MATCHED_PEAKS,
        SCORE_THRESHOLD, PAIRS_MIN_COSINE
                           → analyzed_with (concatenated literal)
      ion_mode             → acquired_in_mode (literal: positive/negative)

    Returns [] on XML parse failure rather than raising, so a malformed
    response doesn't crash a bulk projection job.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    # Build name→value map. GNPS XML uses repeated <parameter name="..."> elems.
    params: dict[str, list[str]] = {}
    for p in root.iter("parameter"):
        name = p.get("name")
        if not name:
            continue
        params.setdefault(name, []).append((p.text or "").strip())

    def first(name: str) -> str | None:
        vs = params.get(name)
        return vs[0] if vs and vs[0] else None

    subject = f"gnps_task:{task_id}"
    out: list[dict[str, Any]] = []

    # 1. workflow → has_processing_software
    workflow = first("workflow")
    if workflow:
        label = (_GNPS_WORKFLOW_LABELS.get(workflow.upper())
                 or canonical_software_name("GNPS")
                 or "GNPS")
        # Always tag the underlying workflow ID in evidence for traceability.
        out.append(_claim(subject, "has_processing_software", label,
                          evidence={"gnps_workflow": workflow},
                          source_doi=source_doi))

    # 2. tolerances + thresholds → analyzed_with (concatenated literal)
    tol_parts: list[str] = []
    for key in ("tolerance.PM_tolerance", "tolerance.Ion_tolerance",
                "MIN_MATCHED_PEAKS", "SCORE_THRESHOLD", "PAIRS_MIN_COSINE"):
        v = first(key)
        if v:
            tol_parts.append(f"{key}={v}")
    if tol_parts:
        out.append(_claim(subject, "analyzed_with", "; ".join(tol_parts),
                          source_doi=source_doi))

    # 3. ion_mode → acquired_in_mode (literal positive/negative)
    ion = first("ion_mode")
    if ion:
        out.append(_claim(subject, "acquired_in_mode", ion.lower(),
                          source_doi=source_doi))

    return out


def fetch_gnps_parameters(
    task_id: str,
    *,
    session: requests.Session | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
    timeout: float = 15.0,
) -> str | None:
    """GET `ManageParameters?task=<task_id>`. Returns raw XML text or None."""
    if not task_id or not task_id.strip():
        return None
    cache_path: Path | None = None
    if cache_dir is not None:
        cache_path = _cache_path((task_id, "parameters"), Path(cache_dir))
        # Parameters cache stores XML as a string in a one-key JSON dict so
        # we can keep the same cache-dir layout as result_json.
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8")).get("xml")
            except (OSError, ValueError):
                pass

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", USER_AGENT)
    try:
        r = sess.get(GNPS_PARAMETERS_URL, params={"task": task_id},
                     timeout=timeout)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    xml_text = r.text

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"xml": xml_text}), encoding="utf-8")
    return xml_text


# ----------- high-level convenience --------------------------------------

def gnps_task_to_claims(
    task_id: str,
    *,
    source_doi: str | None = None,
    annotations_data: dict[str, Any] | None = None,
    parameters_xml: str | None = None,
    session: requests.Session | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
) -> list[dict[str, Any]]:
    """One call → both projections.

    Pass `annotations_data=<dict>` and/or `parameters_xml=<str>` to bypass
    the HTTP layer (useful for offline tests and pre-fetched data).
    """
    claims: list[dict[str, Any]] = []
    if annotations_data is None:
        annotations_data = fetch_gnps_annotations(task_id, session=session,
                                                  cache_dir=cache_dir)
    if annotations_data:
        claims.extend(parse_gnps_annotations(annotations_data.get("blockData") or [],
                                             task_id, source_doi=source_doi))
    if parameters_xml is None:
        parameters_xml = fetch_gnps_parameters(task_id, session=session,
                                               cache_dir=cache_dir)
    if parameters_xml:
        claims.extend(parse_gnps_parameters(parameters_xml, task_id,
                                            source_doi=source_doi))
    return claims
