"""MetabolomicsAdapter — domain-agnostic base metabolomics adapter.

Covers general MS/NMR claims, biomarker associations, and compound enrichment
via the bundled RefMet+BridgeDb compound index. SHACL shapes validate ASB claim
CURIE format only (pipeline RDF validation is upstream's responsibility).
"""
from __future__ import annotations

from importlib.resources import files
from typing import Final

import rdflib

from indicium_adapters_metabolomics._enrichment import COMPOUND_INDEX
from indicium_adapters_metabolomics._namespaces import METABOLOMICS_PREFIXES
from indicium_adapters_metabolomics._registries import (
    accession_to_curie,
    canonical_software_name,
    is_ignored_tool_name,
    is_metabolomics_database,
    is_metabolomics_tool,
)

__all__ = [
    "MetabolomicsAdapter",
    "accession_to_curie",
    "canonical_software_name",
    "is_ignored_tool_name",
    "is_metabolomics_database",
    "is_metabolomics_tool",
]

# Priority order when multiple CURIEs are available for the same compound.
_PRINCIPAL_CURIE_ORDER: Final[tuple[str, ...]] = ("chebi", "hmdb", "pubchem")

# Columns from the TSV that count as cross-references (excludes label/class metadata).
_XREF_COLUMNS: Final[tuple[str, ...]] = (
    "chebi", "hmdb", "kegg", "lipidmaps", "pubchem", "wikidata",
)


class MetabolomicsAdapter:
    """Base metabolomics DomainAdapter (api_version=1).

    Qualifiers cover identification/quantification/biomarker/discrimination/
    metabolism/co-occurrence claims. Enrichment uses the shared RefMet+BridgeDb
    compound index.
    """

    domain_id = "metabolomics"
    api_version = 1

    qualifiers: frozenset[str] = frozenset({
        # Per-compound (claim-level) assertions.
        "identifies",
        "quantifies",
        "is_biomarker_for",
        "discriminates_between",
        "metabolizes",
        "co_occurs_with",
        "found_in_organism",
        "found_in_environment",
        # Study-level assay-metadata qualifiers (v0.4.0). Subject is typically
        # a study or capsule identifier; object is the tool/parameter literal.
        # Added per the 2026-05-24 audit so ASB metabolomics_metadata
        # (processing_software, instrument, ionization_mode,
        # chromatography_type, mass_analyzer) can be projected to claims
        # without requiring the LLM extraction layer.
        "has_processing_software",
        "analyzed_with",
        "acquired_in_mode",
        "chromatographed_on",
        "uses_mass_analyzer",
        # v0.5.0 — three more study/paper-level qualifiers driven by audit 2:
        #   `uses_database`         — separates reference DBs (ChEBI, HMDB,
        #                              MetaboLights, GNPS-LIBRARIES) from
        #                              processing software.
        #   `acquired_from_matrix`  — sample-type / biological matrix
        #                              (urine, serum, feces, plant leaf, soil).
        #   `consolidates_dataset`  — paper → repository accession when one
        #                              publication unifies multiple datasets
        #                              (e.g. a meta-analysis aggregating 15
        #                              MSV deposits).
        "uses_database",
        "acquired_from_matrix",
        "consolidates_dataset",
    })

    ontology_prefixes: dict[str, str] = METABOLOMICS_PREFIXES

    def extraction_context(self) -> str:
        return (
            "Domain: metabolomics. Extra qualifiers available: "
            "identifies, quantifies, is_biomarker_for, discriminates_between, "
            "metabolizes, co_occurs_with, found_in_organism, found_in_environment, "
            "has_processing_software, analyzed_with, acquired_in_mode, "
            "chromatographed_on, uses_mass_analyzer, uses_database, "
            "acquired_from_matrix, consolidates_dataset. "
            "Use canonical compound names (RefMet-compatible, CHEBI-compatible) "
            "for metabolite subjects and objects where possible. "
            "Study-level qualifiers (has_processing_software, analyzed_with, "
            "acquired_in_mode, chromatographed_on, uses_mass_analyzer, "
            "uses_database, acquired_from_matrix, consolidates_dataset) take a "
            "study/capsule/paper ID as subject and a tool / instrument / mode / "
            "database / matrix / accession literal as object (e.g. 'MZmine', "
            "'Q-Exactive HF', 'positive', 'C18 reverse-phase', 'Orbitrap', "
            "'ChEBI', 'serum', 'MSV:MSV000088235')."
        )

    def enrich_claim(self, claim: dict) -> dict:
        """Enrich a claim with CHEBI/HMDB/etc. CURIEs by looking up the subject and
        object names in the bundled RefMet+BridgeDb compound index. Returns a new
        dict; never mutates input."""
        claim = dict(claim)
        if "ontology_terms" in claim:
            claim["ontology_terms"] = dict(claim["ontology_terms"])
        if "xrefs" in claim:
            claim["xrefs"] = dict(claim["xrefs"])
        for slot in ("subject", "object"):
            name = (claim.get(slot) or "").strip()
            if not name:
                continue
            row = COMPOUND_INDEX.lookup(name)
            if not row:
                continue
            for col in _PRINCIPAL_CURIE_ORDER:
                if curie := row.get(col):
                    claim.setdefault("ontology_terms", {})[slot] = curie
                    break
            xrefs = {col: row[col] for col in _XREF_COLUMNS if row.get(col)}
            if xrefs:
                claim.setdefault("xrefs", {})[slot] = xrefs
        return claim

    def shacl_shapes(self) -> rdflib.Graph:
        """Return ASB-claim SHACL shapes (CURIE format validation only)."""
        g = rdflib.Graph()
        ttl = files("indicium_adapters_metabolomics.shapes").joinpath(
            "metabolomics.shapes.ttl"
        )
        g.parse(ttl.open("rb"), format="turtle")
        return g
