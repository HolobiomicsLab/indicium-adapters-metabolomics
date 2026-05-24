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
        "identifies",
        "quantifies",
        "is_biomarker_for",
        "discriminates_between",
        "metabolizes",
        "co_occurs_with",
        "found_in_organism",
        "found_in_environment",
    })

    ontology_prefixes: dict[str, str] = METABOLOMICS_PREFIXES

    def extraction_context(self) -> str:
        return (
            "Domain: metabolomics. Extra qualifiers available: "
            "identifies, quantifies, is_biomarker_for, discriminates_between, "
            "metabolizes, co_occurs_with, found_in_organism, found_in_environment. "
            "Use canonical compound names (RefMet-compatible, CHEBI-compatible) "
            "for metabolite subjects and objects where possible."
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
