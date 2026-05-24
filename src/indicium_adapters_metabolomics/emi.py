"""EMIAdapter — Earth Metabolome Initiative + METRIN-KG adapter.

Covers both ENPKG-style analytical claims (emi:Analysis, emi:MS2Spectrum,
annotation chains) and METRIN-KG-style ecological claims (biotic interactions,
plant traits, body-part qualified observations).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import Final

import rdflib

from indicium_adapters_metabolomics._namespaces import EMI_PREFIXES

_WIKIDATA_QID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^Q\d+$")


@lru_cache(maxsize=1)
def _load_plant_parts() -> dict[str, str]:
    """Lazy-load PO plant-part map from bundled JSON (~1363 entries at v0.2.0)."""
    path = files("indicium_adapters_metabolomics.data").joinpath("_po_terms.json")
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def _load_interaction_types() -> dict[str, str]:
    """Lazy-load RO biotic-interaction map from bundled JSON (~13 entries at v0.2.0)."""
    path = files("indicium_adapters_metabolomics.data").joinpath("_ro_terms.json")
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def _load_wd_organisms() -> dict[str, dict[str, str]]:
    """Lazy-load Wikidata top organisms (~200 entries at v0.2.0).

    Keys: lowercase organism label. Values: {'qid': 'Q...', 'label': 'Original Label'}.
    """
    path = files("indicium_adapters_metabolomics.data").joinpath("_wd_organisms.json")
    return json.loads(path.read_text())


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
            if curie := _load_plant_parts().get(obj):
                claim.setdefault("ontology_terms", {})["object"] = curie

        elif qual in {"mediates_interaction", "interacts_with",
                      "parasitizes", "pollinates"}:
            if curie := _load_interaction_types().get(obj):
                claim.setdefault("ontology_terms", {})["object"] = curie

        # New in v0.2.0: organism-label → WD:Qxxx lookup
        for slot in ("subject", "object"):
            if slot in claim.get("ontology_terms", {}):
                continue   # already tagged (e.g. by QID-pattern detection earlier)
            val = (claim.get(slot) or "").strip().lower()
            if not val:
                continue
            if hit := _load_wd_organisms().get(val):
                claim.setdefault("ontology_terms", {})[slot] = f"WD:{hit['qid']}"

        return claim

    def shacl_shapes(self) -> rdflib.Graph:
        g = rdflib.Graph()
        ttl = files("indicium_adapters_metabolomics.shapes").joinpath(
            "emi.shapes.ttl"
        )
        g.parse(ttl.open("rb"), format="turtle")
        return g
