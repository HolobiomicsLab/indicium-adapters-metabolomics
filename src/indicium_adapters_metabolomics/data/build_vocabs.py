"""Offline maintainer script — regenerate the inline-vocabulary JSON files.

DO NOT run at install or import time. Run manually before a release:

    python -m indicium_adapters_metabolomics.data.build_vocabs

Produces 4 JSON files in this dir:
  _npc_terms.json       — NPClassifier pathways/classes/superclasses → NPC: CURIEs
  _po_terms.json        — Plant Ontology body-part labels → PO: CURIEs
  _ro_terms.json        — Relations Ontology biotic interactions → RO: CURIEs
  _wd_organisms.json    — Top Wikidata species (curated P225 + broad P31 supplement) → {qid, label}

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
    """Top Wikidata species ranked by sitelinks, using a P225 taxon-name lookup.

    Wikidata Query Service times out for any ORDER-BY or sitelinks-FILTER query
    that joins P31=Q16521 with P105 (taxon rank) and wikibase:sitelinks.
    Instead, this function fetches curated well-known species by their scientific
    name (P225 taxon name), de-duplicates to the preferred entity per species,
    and supplemented by a broad no-ORDER-BY P31=Q16521 LIMIT query.

    Returns {lowercase_label: {"qid": "Q...", "label": original_label}}.
    """
    SPARQL_URL = "https://query.wikidata.org/sparql"

    # ---- Tier A: curated species by taxon scientific name (P225) ----
    # Fast: VALUES + P225 uses the property index; no sitelinks join needed.
    # Listed roughly in order of metabolomics / ecological relevance.
    TAXON_NAMES_BATCH1 = [
        "Homo sapiens", "Mus musculus", "Rattus norvegicus", "Drosophila melanogaster",
        "Caenorhabditis elegans", "Saccharomyces cerevisiae", "Arabidopsis thaliana",
        "Escherichia coli", "Apis mellifera", "Malus domestica", "Felis catus",
        "Canis lupus familiaris", "Bos taurus", "Sus scrofa", "Gallus gallus",
        "Oryza sativa", "Triticum aestivum", "Zea mays", "Nicotiana tabacum",
        "Solanum lycopersicum", "Solanum tuberosum", "Glycine max",
    ]
    TAXON_NAMES_BATCH2 = [
        "Vitis vinifera", "Olea europaea", "Coffea arabica", "Camellia sinensis",
        "Oryctolagus cuniculus", "Xenopus laevis", "Equus caballus", "Equus asinus",
        "Ovis aries", "Capra hircus", "Bacillus subtilis", "Pseudomonas aeruginosa",
        "Staphylococcus aureus", "Mycobacterium tuberculosis", "Aspergillus niger",
        "Aspergillus fumigatus", "Penicillium chrysogenum", "Candida albicans",
        "Danio rerio", "Citrus sinensis", "Musa acuminata", "Pisum sativum",
        "Medicago truncatula", "Populus trichocarpa", "Physcomitrella patens",
        "Chlamydomonas reinhardtii", "Synechocystis sp. PCC 6803",
        "Streptomyces coelicolor", "Clostridioides difficile",
        "Helicobacter pylori", "Salmonella enterica",
    ]
    QUERY_TEMPLATE = """
    SELECT ?wd ?wdLabel ?taxonName WHERE {{
      ?wd wdt:P225 ?taxonName .
      VALUES ?taxonName {{ {names} }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 200
    """
    out: dict[str, dict[str, str]] = {}
    # Map scientific name → best QID (prefer entities with a common English label)
    seen_taxon: dict[str, dict[str, str]] = {}

    for batch_num, names in enumerate([TAXON_NAMES_BATCH1, TAXON_NAMES_BATCH2], 1):
        print(f"  fetching P225 taxon batch {batch_num} ({len(names)} names) ...", file=sys.stderr)
        quoted = " ".join(f'"{n}"' for n in names)
        r = requests.get(
            SPARQL_URL,
            params={"format": "json", "query": QUERY_TEMPLATE.format(names=quoted)},
            headers={
                "User-Agent": "indicium-adapters-metabolomics build_vocabs.py",
                "Accept": "application/sparql-results+json",
            },
            timeout=90,
        )
        r.raise_for_status()
        bindings = r.json()["results"]["bindings"]
        print(f"    got {len(bindings)} rows", file=sys.stderr)
        for b in bindings:
            raw_qid = b["wd"]["value"].rsplit("/", 1)[-1]
            # Skip lexeme-sense nodes (L...-S... format)
            if not raw_qid.startswith("Q"):
                continue
            label = b.get("wdLabel", {}).get("value", "").strip()
            taxon = b.get("taxonName", {}).get("value", "").strip()
            if not label or not taxon:
                continue
            # De-duplicate: prefer entry with a common-name label (not just the taxon name)
            if taxon not in seen_taxon:
                seen_taxon[taxon] = {"qid": raw_qid, "label": label, "taxon": taxon}
            else:
                prev = seen_taxon[taxon]
                # Prefer an English common name (different from the taxon name)
                prev_taxon_lower = prev["taxon"].lower()
                if label.lower() != taxon.lower() and prev["label"].lower() == prev_taxon_lower:
                    seen_taxon[taxon] = {"qid": raw_qid, "label": label, "taxon": taxon}

    for entry in seen_taxon.values():
        key = entry["label"].lower()
        if key not in out:
            out[key] = {"qid": entry["qid"], "label": entry["label"]}
        # Also index by scientific name so lookups by taxon name work
        sci_key = entry["taxon"].lower()
        if sci_key not in out:
            out[sci_key] = {"qid": entry["qid"], "label": entry["taxon"]}

    # ---- Tier B: broad supplement via simple P31=Q16521 with high LIMIT ----
    # No sitelinks filter, no ORDER BY — just a large fast scan.
    BROAD_QUERY = """
    SELECT ?wd ?wdLabel WHERE {
      ?wd wdt:P31 wd:Q16521 .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    LIMIT 400
    """
    print("  fetching broad P31=Q16521 supplement ...", file=sys.stderr)
    try:
        r2 = requests.get(
            SPARQL_URL,
            params={"format": "json", "query": BROAD_QUERY},
            headers={
                "User-Agent": "indicium-adapters-metabolomics build_vocabs.py",
                "Accept": "application/sparql-results+json",
            },
            timeout=90,
        )
        r2.raise_for_status()
        bindings2 = r2.json()["results"]["bindings"]
        print(f"    got {len(bindings2)} rows", file=sys.stderr)
        for b in bindings2:
            qid = b["wd"]["value"].rsplit("/", 1)[-1]
            if not qid.startswith("Q"):
                continue
            label = b.get("wdLabel", {}).get("value", "").strip()
            if not label:
                continue
            key = label.lower()
            if key not in out:
                out[key] = {"qid": qid, "label": label}
    except Exception as exc:
        print(f"    broad supplement failed ({exc}); skipping", file=sys.stderr)

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
