"""GNPS ProteoSAFe + GNPS2 datasette integration.

Endpoints + parsers:

* `result_json.jsp?task=<id>&view=view_all_annotations_DB` → library hits.
  Projects to `spectral_match` claims with MQScore + SharedPeaks evidence.
* `ManageParameters?task=<id>` → run-parameter XML. Projects workflow name
  (canonicalised through the v0.5.0 software registry) + tolerances + ion
  mode to study-level qualifiers (`has_processing_software`,
  `acquired_in_mode`).
* `result_json.jsp?...view=view_all_clusters_withID_beta` → per-cluster
  parent mass / RT / charge / component (v0.7.0 → `has_feature`).
* `result_json.jsp?...view=view_network_pairs` → MN edges (v0.7.0 →
  `structurally_related_to`, undirected canonicalised).
* GNPS2 datasette `datasetcache/uniquemri.json` → per-file MS hardware.

Public surface:
    parse_gnps_annotations / fetch_gnps_annotations
    parse_gnps_parameters / fetch_gnps_parameters
    parse_gnps_clusters / fetch_gnps_clusters                  (v0.7.0)
    parse_gnps_network_pairs / fetch_gnps_network_pairs        (v0.7.0)
    gnps_task_to_claims(task_id, *, views=(...))
    datasetcache_row_to_claims / fetch_datasetcache_row / datasetcache_to_claims
"""
from __future__ import annotations

from indicium_adapters_metabolomics.gnps.datasetcache import (
    DATASETCACHE_BASE,
    datasetcache_row_to_claims,
    datasetcache_to_claims,
    fetch_datasetcache_row,
)
from indicium_adapters_metabolomics.gnps.parser import (
    GNPS_PARAMETERS_URL,
    GNPS_RESULT_JSON_URL,
    GNPS_VIEW_ANNOTATIONS,
    GNPS_VIEW_CLUSTERS,
    GNPS_VIEW_PAIRS,
    GNPS_VIEW_PARAMETERS,
    fetch_gnps_annotations,
    fetch_gnps_clusters,
    fetch_gnps_network_pairs,
    fetch_gnps_parameters,
    gnps_task_to_claims,
    parse_gnps_annotations,
    parse_gnps_clusters,
    parse_gnps_network_pairs,
    parse_gnps_parameters,
)

__all__ = [
    "DATASETCACHE_BASE",
    "GNPS_PARAMETERS_URL",
    "GNPS_RESULT_JSON_URL",
    "GNPS_VIEW_ANNOTATIONS",
    "GNPS_VIEW_CLUSTERS",
    "GNPS_VIEW_PAIRS",
    "GNPS_VIEW_PARAMETERS",
    "datasetcache_row_to_claims",
    "datasetcache_to_claims",
    "fetch_datasetcache_row",
    "fetch_gnps_annotations",
    "fetch_gnps_clusters",
    "fetch_gnps_network_pairs",
    "fetch_gnps_parameters",
    "gnps_task_to_claims",
    "parse_gnps_annotations",
    "parse_gnps_clusters",
    "parse_gnps_network_pairs",
    "parse_gnps_parameters",
]
