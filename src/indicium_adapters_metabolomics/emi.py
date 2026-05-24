"""EMIAdapter — Earth Metabolome Initiative + METRIN-KG adapter.

Covers both ENPKG-style analytical claims (emi:Analysis, emi:MS2Spectrum,
annotation chains) and METRIN-KG-style ecological claims (biotic interactions,
plant traits, body-part qualified observations).
"""
from __future__ import annotations

import re
from importlib.resources import files
from typing import Final

import rdflib

from indicium_adapters_metabolomics._namespaces import EMI_PREFIXES

_WIKIDATA_QID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^Q\d+$")

# Subset of plant-part names → PO: CURIEs (~10 common parts; expand in roadmap).
_PLANT_PARTS: Final[dict[str, str]] = {
    "leaf":           "PO:0025034",
    "stem":           "PO:0009047",
    "root":           "PO:0009005",
    "flower":         "PO:0009046",
    "fruit":          "PO:0009001",
    "seed":           "PO:0009010",
    "bark":           "PO:0004518",
    "wood":           "PO:0005352",
    "bud":            "PO:0000055",
    "inflorescence":  "PO:0009049",
}

# Subset of interaction types → RO: / emi: CURIEs.
_INTERACTION_TYPES: Final[dict[str, str]] = {
    "pollination":   "RO:0002455",   # pollinates
    "parasitism":    "RO:0002444",   # parasite of
    "predation":     "RO:0002458",   # preys on
    "herbivory":     "RO:0002470",   # eats
    "symbiosis":     "RO:0002439",   # in symbiosis with
    "mutualism":     "RO:0002442",   # mutualistically interacts with
    "commensalism":  "RO:0002441",   # commensally interacts with
    "competition":   "RO:0002419",   # competitor of
    "hyperparasitism": "RO:0002553", # hyperparasite of
    "allelopathy":   "emi:Allelopathy",
}


class EMIAdapter:
    """EMI / METRIN-KG DomainAdapter (api_version=1)."""

    domain_id = "emi"
    api_version = 1

    qualifiers: frozenset[str] = frozenset({
        # ENPKG / analytical
        "annotates_spectrum",
        "has_chemical_class",
        "found_in_species",
        "cosine_similarity",
        "in_extract_sample",
        # METRIN-KG / ecological
        "mediates_interaction",
        "interacts_with",
        "parasitizes",
        "pollinates",
        "associated_with_trait",
        "found_in_plant_part",
        "has_developmental_stage",
        "has_phenotype",
    })

    ontology_prefixes: dict[str, str] = EMI_PREFIXES

    def extraction_context(self) -> str:
        return (
            "Domain: emi (Earth Metabolome Initiative + METRIN-KG). "
            "Covers analytical claims (annotates_spectrum, has_chemical_class, "
            "found_in_species, cosine_similarity, in_extract_sample) AND "
            "ecological claims (mediates_interaction, interacts_with, "
            "parasitizes, pollinates, associated_with_trait, found_in_plant_part, "
            "has_developmental_stage, has_phenotype). Use Wikidata QIDs (Q\\d+) "
            "for taxon identity, PO: for plant parts, RO: for biotic interactions."
        )

    def enrich_claim(self, claim: dict) -> dict:
        claim = dict(claim)
        if "ontology_terms" in claim:
            claim["ontology_terms"] = dict(claim["ontology_terms"])
        qual = claim.get("qualifier", "")

        for slot in ("subject", "object"):
            val = (claim.get(slot) or "").strip()
            if not val:
                continue
            if _WIKIDATA_QID_PATTERN.match(val):
                claim.setdefault("ontology_terms", {})[slot] = f"WD:{val}"

        obj = (claim.get("object") or "").strip().lower()

        if qual == "found_in_plant_part":
            if curie := _PLANT_PARTS.get(obj):
                claim.setdefault("ontology_terms", {})["object"] = curie

        elif qual in {"mediates_interaction", "interacts_with",
                      "parasitizes", "pollinates"}:
            if curie := _INTERACTION_TYPES.get(obj):
                claim.setdefault("ontology_terms", {})["object"] = curie

        return claim

    def shacl_shapes(self) -> rdflib.Graph:
        g = rdflib.Graph()
        ttl = files("indicium_adapters_metabolomics.shapes").joinpath(
            "emi.shapes.ttl"
        )
        g.parse(ttl.open("rb"), format="turtle")
        return g
