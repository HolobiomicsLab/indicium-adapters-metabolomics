"""ReDU (Reusable Data — UCSD) integration.

Per-file sample-metadata lookup for public MassIVE deposits. Projects ReDU's
curated NCBITaxonomy / UBERON body-part / DOID disease / mass-spec / chromatography
fields into existing adapter qualifiers (`found_in_organism`,
`acquired_from_matrix`, `is_biomarker_for`, `analyzed_with`, `acquired_in_mode`,
`chromatographed_on`).

Public surface:
    redu_lookup(filename, *, session=None, cache_dir=...) -> dict | None
    redu_to_claims(filename, study_id, *, source_doi=None, sample_info=None)
                                                              -> list[dict]
"""
from __future__ import annotations

from indicium_adapters_metabolomics.redu.parser import (
    REDU_GH_LIST_URL,
    REDU_GH_TSV_URL,
    list_redu_msvs,
    redu_lookup,
    redu_sample_to_claims,
    redu_to_claims,
)

__all__ = ["REDU_GH_LIST_URL", "REDU_GH_TSV_URL", "list_redu_msvs",
           "redu_lookup", "redu_sample_to_claims", "redu_to_claims"]
