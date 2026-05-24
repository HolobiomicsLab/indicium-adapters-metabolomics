"""Offline maintainer script — regenerate refmet_compounds.tsv from upstream sources.

DO NOT run at install or import time. Run manually before a release:

    python -m indicium_adapters_metabolomics.data.build_data

Design: the output is a SINGLE merged TSV (refmet_compounds.tsv). RefMet rows and
BridgeDb cross-references are joined on InChIKey at build time; runtime
(_enrichment.CompoundIndex) loads only that one file. There is intentionally no
separate bridgedb_metabolites.tsv shipped — keeping a single file simplifies
lookup and avoids stale-key drift between two tables.

Pulls fresh data from:
- RefMet:   https://www.metabolomicsworkbench.org/databases/refmet/refmet_download.php
- BridgeDb: https://bridgedb.github.io/data/gene_database/metabolites-latest.tsv

Writes refmet_compounds.tsv with columns:
    name_lower, refmet_name, inchikey, inchikey2d,
    chebi, hmdb, kegg, lipidmaps, pubchem, wikidata,
    chemical_class, super_class, pathway
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REFMET_URL = "https://www.metabolomicsworkbench.org/databases/refmet/refmet_download.php"
BRIDGEDB_URL = "https://bridgedb.github.io/data/gene_database/metabolites-latest.tsv"

OUTPUT_PATH = Path(__file__).parent / "refmet_compounds.tsv"
COLUMNS = [
    "name_lower", "refmet_name", "inchikey", "inchikey2d",
    "chebi", "hmdb", "kegg", "lipidmaps", "pubchem", "wikidata",
    "chemical_class", "super_class", "pathway",
]


def fetch_refmet() -> list[dict[str, str]]:
    """Download and parse the RefMet TSV. Returns one dict per metabolite."""
    raise NotImplementedError(
        "Wire up urllib.request + csv parser when running a real refresh. "
        "Stub kept for v0.1.0; the bundled TSV is hand-curated."
    )


def fetch_bridgedb() -> list[dict[str, str]]:
    """Download and parse the BridgeDb metabolite mappings."""
    raise NotImplementedError(
        "Wire up urllib.request + csv parser when running a real refresh."
    )


def merge_on_inchikey(refmet: list[dict[str, str]],
                      bridgedb: list[dict[str, str]]) -> list[dict[str, str]]:
    """Merge RefMet + BridgeDb on InChIKey to produce one row per compound."""
    raise NotImplementedError("Wire up when fetch_* are implemented.")


def write_tsv(rows: list[dict[str, str]], path: Path = OUTPUT_PATH) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in COLUMNS})


def main() -> int:
    refmet = fetch_refmet()
    bridgedb = fetch_bridgedb()
    merged = merge_on_inchikey(refmet, bridgedb)
    write_tsv(merged)
    print(f"Wrote {len(merged)} rows to {OUTPUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
