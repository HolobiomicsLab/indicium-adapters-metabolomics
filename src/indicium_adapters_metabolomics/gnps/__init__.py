"""GNPS ProteoSAFe integration.

Two REST endpoints, two parsers:

* `result_json.jsp?task=<id>&view=view_all_annotations_DB` → library hits.
  Projects to `spectral_match` claims with MQScore + SharedPeaks evidence.
* `ManageParameters?task=<id>` → run-parameter XML. Projects workflow name
  (canonicalised through the v0.5.0 software registry) + tolerances + ion
  mode to study-level qualifiers (`has_processing_software`, `analyzed_with`,
  `acquired_in_mode`).

Public surface:
    parse_gnps_annotations(blockdata, task_id, *, source_doi=None) -> list[Claim]
    fetch_gnps_annotations(task_id, *, session=None, cache_dir=...) -> dict | None
    parse_gnps_parameters(xml_text, task_id, *, source_doi=None) -> list[Claim]
    fetch_gnps_parameters(task_id, *, session=None, cache_dir=...) -> str | None
"""
from __future__ import annotations

from indicium_adapters_metabolomics.gnps.parser import (
    GNPS_PARAMETERS_URL,
    GNPS_RESULT_JSON_URL,
    fetch_gnps_annotations,
    fetch_gnps_parameters,
    gnps_task_to_claims,
    parse_gnps_annotations,
    parse_gnps_parameters,
)

__all__ = [
    "GNPS_PARAMETERS_URL",
    "GNPS_RESULT_JSON_URL",
    "fetch_gnps_annotations",
    "fetch_gnps_parameters",
    "gnps_task_to_claims",
    "parse_gnps_annotations",
    "parse_gnps_parameters",
]
