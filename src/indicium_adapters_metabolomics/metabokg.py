"""MetaboKGAdapter — MetaboKG-flavored claim adapter.

Covers GNPS/FBMN spectral match claims, NPC chemical classification,
MSI annotation confidence levels, and provenance to GNPS analyses.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import Final

import rdflib

from indicium_adapters_metabolomics._namespaces import METABOKG_PREFIXES


@lru_cache(maxsize=1)
def _load_npc_pathways() -> dict[str, str]:
    """Lazy-load NPC term map from bundled JSON (~771 entries at v0.2.0)."""
    path = files("indicium_adapters_metabolomics.data").joinpath("_npc_terms.json")
    return json.loads(path.read_text())

_ANNOTATION_LEVELS: Final[frozenset[str]] = frozenset({
    "level_1", "level_2", "level_3",
})

_USI_PATTERN: Final[re.Pattern[str]] = re.compile(r"^mzspec:", re.IGNORECASE)
_INCHIKEY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$"
)


class MetaboKGAdapter:
    """MetaboKG-flavored DomainAdapter (api_version=1)."""

    domain_id = "metabokg"
    api_version = 1

    qualifiers: frozenset[str] = frozenset({
        "spectral_match",
        "has_annotation_level",
        "classified_as",
        "annotated_in",
        "has_feature",
        "structurally_related_to",
        "shares_fragment_with",
    })

    ontology_prefixes: dict[str, str] = METABOKG_PREFIXES

    def extraction_context(self) -> str:
        return (
            "Domain: metabokg (MetaboKG analysis-centric metabolomics). "
            "Extra qualifiers: spectral_match, has_annotation_level, "
            "classified_as, annotated_in, has_feature, structurally_related_to, "
            "shares_fragment_with. Use USI (mzspec:...) for spectrum references, "
            "InChIKey for structure identity, NPC: prefix for chemical class, "
            "MSI annotation levels are level_1/level_2/level_3."
        )

    def enrich_claim(self, claim: dict) -> dict:
        claim = dict(claim)
        if "ontology_terms" in claim:
            claim["ontology_terms"] = dict(claim["ontology_terms"])
        qual = claim.get("qualifier", "")
        obj = (claim.get("object") or "").strip()

        if qual == "classified_as":
            if curie := _load_npc_pathways().get(obj.lower()):
                claim.setdefault("ontology_terms", {})["object"] = curie

        elif qual == "has_annotation_level":
            claim["enum_valid"] = obj.lower() in _ANNOTATION_LEVELS

        elif qual == "spectral_match":
            if _USI_PATTERN.match(obj):
                claim.setdefault("ontology_terms", {})["object"] = f"USI:{obj}"
            elif _INCHIKEY_PATTERN.match(obj):
                claim.setdefault("ontology_terms", {})["object"] = f"InChIKey:{obj}"

        return claim

    def shacl_shapes(self) -> rdflib.Graph:
        g = rdflib.Graph()
        ttl = files("indicium_adapters_metabolomics.shapes").joinpath(
            "metabokg.shapes.ttl"
        )
        g.parse(ttl.open("rb"), format="turtle")
        return g
