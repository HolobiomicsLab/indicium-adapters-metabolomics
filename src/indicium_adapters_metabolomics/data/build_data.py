"""Offline maintainer script — regenerate refmet_compounds.tsv from Wikidata.

DO NOT run at install or import time. Run manually before a release:

    python -m indicium_adapters_metabolomics.data.build_data

Strategy (v0.2.0): Wikidata SPARQL is the primary cross-reference source. It
exposes all the major metabolite databases as properties:
  P235  → InChIKey
  P683  → ChEBI
  P2057 → HMDB
  P665  → KEGG
  P2063 → LIPID MAPS
  P662  → PubChem CID

The Wikidata Query Service has a 60s timeout; we chunk by ChEBI-ID range so
each subquery stays under the limit.

RefMet integration is intentionally deferred — Wikidata's rdfs:label and the
ChEBI-recommended name are sufficient for the `name_lower` column at this
stage. RefMet name canonicalization comes in v0.3.0.

Output: refmet_compounds.tsv (~30k rows) at the package data dir.
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from typing import Iterable

import requests

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = (
    "indicium-adapters-metabolomics/0.2.0 build_data.py "
    "(https://github.com/HolobiomicsLab/indicium-adapters-metabolomics)"
)
OUTPUT_PATH = Path(__file__).parent / "refmet_compounds.tsv"
COLUMNS = [
    "name_lower", "refmet_name", "inchikey", "inchikey2d",
    "chebi", "hmdb", "kegg", "lipidmaps", "pubchem", "wikidata",
    "chemical_class", "super_class", "pathway",
]

# Chunked query — fetch by ChEBI ID range to keep each subquery under 60s.
# At ~30k ChEBI-mapped compounds in Wikidata, chunking by 5k IDs yields ~6 requests.
CHEBI_RANGES = [
    (1, 5_000), (5_001, 25_000), (25_001, 50_000),
    (50_001, 100_000), (100_001, 200_000), (200_001, 500_000),
]


SPARQL_TEMPLATE = """
SELECT ?wd ?wdLabel ?inchikey ?chebi ?hmdb ?kegg ?lmid ?cid WHERE {{
  ?wd wdt:P683 ?chebi .
  FILTER(xsd:integer(?chebi) >= {lo} && xsd:integer(?chebi) <= {hi})
  OPTIONAL {{ ?wd wdt:P235  ?inchikey . }}
  OPTIONAL {{ ?wd wdt:P2057 ?hmdb . }}
  OPTIONAL {{ ?wd wdt:P665  ?kegg . }}
  OPTIONAL {{ ?wd wdt:P2063 ?lmid . }}
  OPTIONAL {{ ?wd wdt:P662  ?cid . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def fetch_wikidata_chunk(lo: int, hi: int) -> list[dict[str, str]]:
    """Query Wikidata SPARQL for compounds with ChEBI IDs in [lo, hi].

    Returns one dict per row. Retries up to 3 times on transient HTTP errors.
    """
    query = SPARQL_TEMPLATE.format(lo=lo, hi=hi)
    for attempt in range(3):
        try:
            r = requests.get(
                WIKIDATA_SPARQL,
                params={"format": "json", "query": query},
                headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
                timeout=120,
            )
            r.raise_for_status()
            bindings = r.json()["results"]["bindings"]
            return [_extract_row(b) for b in bindings]
        except requests.HTTPError as exc:
            if attempt == 2:
                raise
            print(f"  retry {attempt + 1}/3 after {exc!r}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    return []


def _extract_row(binding: dict) -> dict[str, str]:
    """Pull values out of one SPARQL JSON binding into our flat row dict."""
    def v(key: str) -> str:
        return binding.get(key, {}).get("value", "")

    wd_uri = v("wd")
    qid = wd_uri.rsplit("/", 1)[-1] if wd_uri else ""
    inchikey = v("inchikey")
    label = v("wdLabel")
    return {
        "name_lower":     label.lower() if label else "",
        "refmet_name":    "",  # deferred to v0.3.0
        "inchikey":       inchikey,
        "inchikey2d":     inchikey[:14] if len(inchikey) >= 14 else "",
        "chebi":          f"CHEBI:{v('chebi')}" if v("chebi") else "",
        "hmdb":           v("hmdb"),
        "kegg":           v("kegg"),
        "lipidmaps":      v("lmid"),
        "pubchem":        f"PUBCHEM:{v('cid')}" if v("cid") else "",
        "wikidata":       f"WD:{qid}" if qid else "",
        "chemical_class": "",   # populated by future enrichment
        "super_class":    "",
        "pathway":        "",
    }


def fetch_all_wikidata() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for lo, hi in CHEBI_RANGES:
        print(f"Fetching ChEBI:{lo}..{hi} ...", file=sys.stderr)
        chunk = fetch_wikidata_chunk(lo, hi)
        print(f"  got {len(chunk)} rows", file=sys.stderr)
        rows.extend(chunk)
    return rows


def deduplicate_on_inchikey(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Drop duplicates: same InChIKey → keep first."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for r in rows:
        ik = r.get("inchikey", "")
        if ik and ik in seen:
            continue
        if ik:
            seen.add(ik)
        out.append(r)
    return out


def write_tsv(rows: list[dict[str, str]], path: Path = OUTPUT_PATH) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in COLUMNS})


def main() -> int:
    print(f"Querying Wikidata SPARQL: {WIKIDATA_SPARQL}", file=sys.stderr)
    rows = fetch_all_wikidata()
    print(f"\nFetched {len(rows)} raw rows", file=sys.stderr)
    rows = deduplicate_on_inchikey(rows)
    print(f"After InChIKey dedupe: {len(rows)} rows", file=sys.stderr)
    write_tsv(rows)
    print(f"Wrote {OUTPUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
