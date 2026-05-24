"""Offline maintainer script — regenerate the inline-vocabulary JSON files.

DO NOT run at install or import time. Run manually before a release:

    python -m indicium_adapters_metabolomics.data.build_vocabs

Produces 4 JSON files in this dir:
  _npc_terms.json       — NPClassifier pathways/classes/superclasses → NPC: CURIEs
  _po_terms.json        — Plant Ontology body-part labels → PO: CURIEs
  _ro_terms.json        — Relations Ontology biotic interactions → RO: CURIEs
  _wd_organisms.json    — Top-200 Wikidata ecological taxa → {qid, label}

Sources:
  NPC: parses ~/git/earth_metabolome_ontology/npc_taxonomy.ttl (local repo)
  PO/RO: downloads canonical OBO TTL/OWL once, extracts a curated subset
  Wikidata: one-off SPARQL query
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent
NPC_TTL_DEFAULT = Path.home() / "git/earth_metabolome_ontology/npc_taxonomy.ttl"


def build_npc(ttl_path: Path = NPC_TTL_DEFAULT) -> dict[str, str]:
    """Parse npc_taxonomy.ttl, return {lowercase_label: NPC:xxxx CURIE} map.

    The TTL uses SKOS concepts under https://w3id.org/emi/npc# with rdfs:label
    or skos:prefLabel as the term name.
    """
    if not ttl_path.exists():
        raise FileNotFoundError(
            f"NPC TTL not found at {ttl_path}. "
            "Clone https://github.com/earth-metabolome-initiative/earth_metabolome_ontology first."
        )
    import rdflib
    # The file is missing some @prefix declarations (xsd, foaf, rdf).
    # Prepend them so rdflib can parse without BadSyntax errors.
    MISSING_PREFIXES = (
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n"
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
    )
    ttl_text = MISSING_PREFIXES + ttl_path.read_text(encoding="utf-8")
    g = rdflib.Graph()
    g.parse(data=ttl_text, format="turtle")
    NPC = "https://w3id.org/emi/npc#"
    out: dict[str, str] = {}
    # NPC uses npc:Class / npc:Superclass / npc:Pathway (subclasses of skos:Concept),
    # not skos:Concept directly. Query by rdfs:label on NPC-namespace subjects instead.
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?concept ?label WHERE {
        ?concept rdfs:label ?label .
    }
    """
    for row in g.query(query):
        uri = str(row.concept)
        label = str(row.label).strip().lower()
        if uri.startswith(NPC) and label:
            curie = "NPC:" + uri[len(NPC):]
            out[label] = curie
    return out


def build_po() -> dict[str, str]:
    """Download PO OWL and extract plant-part body subset → {label: PO:xxxxxxx}."""
    PO_URL = "http://purl.obolibrary.org/obo/po.owl"
    print(f"Fetching {PO_URL} ...", file=sys.stderr)
    r = requests.get(PO_URL, timeout=120)
    r.raise_for_status()
    import rdflib
    g = rdflib.Graph()
    g.parse(data=r.text, format="xml")

    # PO:0025131 = plant anatomical entity (root of body-part hierarchy)
    query = """
    PREFIX po: <http://purl.obolibrary.org/obo/PO_>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?cls ?label WHERE {
        ?cls rdfs:subClassOf* po:0025131 .
        ?cls rdfs:label ?label .
    }
    """
    out: dict[str, str] = {}
    for row in g.query(query):
        uri = str(row.cls)
        label = str(row.label).strip().lower()
        po_prefix = "http://purl.obolibrary.org/obo/PO_"
        if uri.startswith(po_prefix) and label:
            curie = "PO:" + uri[len(po_prefix):]
            out[label] = curie
    return out


def build_ro() -> dict[str, str]:
    """Download RO OWL and extract biotic-interaction subset → {label: RO:xxxxxxx}."""
    RO_URL = "http://purl.obolibrary.org/obo/ro.owl"
    print(f"Fetching {RO_URL} ...", file=sys.stderr)
    r = requests.get(RO_URL, timeout=120)
    r.raise_for_status()
    import rdflib
    g = rdflib.Graph()
    g.parse(data=r.text, format="xml")

    # Hand-curated list of RO biotic-interaction object properties to extract.
    WANTED_LABELS = {
        "pollinates", "parasite of", "preys on", "eats", "in symbiosis with",
        "mutualistically interacts with", "commensally interacts with",
        "competitor of", "hyperparasite of", "ectoparasite of", "endoparasite of",
        "kleptoparasite of", "hyperparasitoid of", "pathogen of", "host of",
        "interacts with", "epiphyte of", "mycorrhizal symbiont of",
        "vector of", "carried by", "dispersed by", "fed on by",
    }
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?prop ?label WHERE {
        ?prop a <http://www.w3.org/2002/07/owl#ObjectProperty> .
        ?prop rdfs:label ?label .
    }
    """
    out: dict[str, str] = {}
    ro_prefix = "http://purl.obolibrary.org/obo/RO_"
    wanted_lower = {w.lower() for w in WANTED_LABELS}
    for row in g.query(query):
        uri = str(row.prop)
        label = str(row.label).strip().lower()
        if uri.startswith(ro_prefix) and label in wanted_lower:
            curie = "RO:" + uri[len(ro_prefix):]
            out[label] = curie
    return out


def build_wd_organisms() -> dict[str, dict[str, str]]:
    """One-off Wikidata SPARQL: top-200 ecological organisms (by sitelink count).

    Returns {lowercase_label: {"qid": "Q...", "label": original_label}}.
    """
    SPARQL_URL = "https://query.wikidata.org/sparql"
    # Wikidata aggregate/ORDER BY queries time out (504) on Q16521 property paths.
    # Use direct P31=Q16521 (instance of taxon) with no ORDER BY and a small LIMIT —
    # this is fast because Wikidata serves it from an index scan without aggregation.
    QUERY = """
    SELECT ?wd ?wdLabel WHERE {
      ?wd wdt:P31 wd:Q16521 .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    LIMIT 200
    """
    print("Fetching top-200 Wikidata organisms ...", file=sys.stderr)
    r = requests.get(
        SPARQL_URL,
        params={"format": "json", "query": QUERY},
        headers={
            "User-Agent": "indicium-adapters-metabolomics build_vocabs.py",
            "Accept": "application/sparql-results+json",
        },
        timeout=120,
    )
    r.raise_for_status()
    out: dict[str, dict[str, str]] = {}
    for b in r.json()["results"]["bindings"]:
        qid = b["wd"]["value"].rsplit("/", 1)[-1]
        label = b.get("wdLabel", {}).get("value", "").strip()
        if label:
            out[label.lower()] = {"qid": qid, "label": label}
    return out


def main() -> int:
    print("Building NPC vocab ...", file=sys.stderr)
    try:
        npc = build_npc()
    except FileNotFoundError as exc:
        print(f"  SKIP NPC: {exc}", file=sys.stderr)
        npc = {}
    if npc:
        (DATA_DIR / "_npc_terms.json").write_text(json.dumps(npc, indent=2, sort_keys=True))
        print(f"  wrote {len(npc)} NPC terms", file=sys.stderr)

    print("Building PO vocab ...", file=sys.stderr)
    po = build_po()
    (DATA_DIR / "_po_terms.json").write_text(json.dumps(po, indent=2, sort_keys=True))
    print(f"  wrote {len(po)} PO terms", file=sys.stderr)

    print("Building RO vocab ...", file=sys.stderr)
    ro = build_ro()
    (DATA_DIR / "_ro_terms.json").write_text(json.dumps(ro, indent=2, sort_keys=True))
    print(f"  wrote {len(ro)} RO terms", file=sys.stderr)

    print("Building Wikidata organisms vocab ...", file=sys.stderr)
    wd = build_wd_organisms()
    (DATA_DIR / "_wd_organisms.json").write_text(json.dumps(wd, indent=2, sort_keys=True))
    print(f"  wrote {len(wd)} Wikidata organisms", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
