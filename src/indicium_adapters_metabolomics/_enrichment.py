"""CompoundIndex — lazy in-memory lookup for metabolite name/InChIKey → cross-references.

Loads `data/refmet_compounds.tsv` on first lookup. Module-level singleton
`COMPOUND_INDEX` shared across all adapter instances and adapter classes.
Pure function: no I/O during lookup, no network anywhere.
"""
from __future__ import annotations

import csv
import json
from importlib.resources import files


class CompoundIndex:
    """Compound name / InChIKey → cross-reference row lookup.

    Loads lazily on first `.lookup()` call. Returns `None` for unknown queries.
    Rows are dicts with keys matching the TSV column names; downstream code is
    responsible for selecting which CURIE to use (CHEBI / HMDB / PUBCHEM, etc.).
    """

    # Cross-reference columns the by-CURIE index is built from, paired with the
    # CURIE prefix to use when the TSV stores a bare ID (no colon). The
    # Wikidata-derived TSV stores chebi / pubchem / wikidata with the prefix
    # baked in (e.g. "CHEBI:17234"), but hmdb / kegg / lipidmaps as bare
    # identifiers (e.g. "HMDB0000122", "C00031", "LMPK12070051"); we normalise
    # both forms so consumers can pass either "CHEBI:17234" or "HMDB:HMDB0000122"
    # to enrich_claim() and get a hit.
    _CURIE_COLUMNS: tuple[tuple[str, str], ...] = (
        ("chebi",     "CHEBI"),
        ("hmdb",      "HMDB"),
        ("pubchem",   "PUBCHEM"),
        ("kegg",      "KEGG"),
        ("wikidata",  "WD"),
        ("lipidmaps", "LIPIDMAPS"),
    )

    def __init__(self) -> None:
        self._by_name: dict[str, dict[str, str]] = {}
        self._by_inchikey: dict[str, dict[str, str]] = {}
        self._by_inchikey2d: dict[str, dict[str, str]] = {}
        # CURIE-indexed lookups so enrich_claim() can resolve subjects already
        # in CURIE form (e.g. "CHEBI:17234") to the full cross-reference row,
        # not just bare compound names.
        self._by_curie: dict[str, dict[str, str]] = {}
        self._loaded: bool = False

    def _load(self) -> None:
        if self._loaded:
            return
        tsv_path = files("indicium_adapters_metabolomics.data").joinpath(
            "refmet_compounds.tsv"
        )
        with tsv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for raw_row in reader:
                # Drop empty string values for cleaner downstream access
                row = {k: v for k, v in raw_row.items() if v}
                name = row.get("name_lower", "").strip().lower()
                if name:
                    self._by_name[name] = row
                ik = row.get("inchikey", "").strip()
                if ik:
                    self._by_inchikey[ik] = row
                    if len(ik) >= 14:
                        self._by_inchikey2d[ik[:14]] = row
                for col, prefix in self._CURIE_COLUMNS:
                    val = row.get(col, "").strip()
                    if not val:
                        continue
                    curie = val if ":" in val else f"{prefix}:{val}"
                    # First write wins on collision (TSV row order). Index both
                    # the canonical form and its uppercase variant so consumers
                    # can pass either "CHEBI:17234" or "chebi:17234".
                    self._by_curie.setdefault(curie, row)
                    self._by_curie.setdefault(curie.upper(), row)
        # Synonym layer (v0.4.0): names a paper or LLM might emit that don't
        # match the Wikidata-derived canonical label. Each alias is aliased
        # into `_by_name` to point at the same row, so lookup() needs no
        # extra logic. Targets are verified at load-time; unknown targets
        # are silently skipped (defensive against TSV regeneration).
        syn_path = files("indicium_adapters_metabolomics.data").joinpath(
            "_synonyms.json"
        )
        synonyms = json.loads(syn_path.read_text(encoding="utf-8"))
        for alias, target in synonyms.items():
            if alias.startswith("_"):  # skip _meta block
                continue
            target_l = target.strip().lower()
            row = self._by_name.get(target_l)
            if row is None:
                continue
            self._by_name.setdefault(alias.strip().lower(), row)
        self._loaded = True

    def lookup(self, query: str) -> dict[str, str] | None:
        """Look up a compound by name (case-insensitive), full InChIKey (27 chars),
        InChIKey2D (14 chars), or CURIE (e.g. "CHEBI:17234", "HMDB:HMDB0000122",
        "PUBCHEM:5793", "KEGG:C00031", "WD:Q37525"). Returns the matching row
        dict, or None."""
        if not query or not query.strip():
            return None
        self._load()
        q = query.strip()
        # CURIE-shaped queries: try as-is, then upper-cased prefix.
        if ":" in q and not q.startswith("InChI="):
            if hit := self._by_curie.get(q):
                return hit
            if hit := self._by_curie.get(q.upper()):
                return hit
        ql = q.lower()
        if hit := self._by_name.get(ql):
            return hit
        if hit := self._by_inchikey.get(q):
            return hit
        if len(q) >= 14:
            if hit := self._by_inchikey2d.get(q[:14]):
                return hit
        return None


COMPOUND_INDEX: CompoundIndex = CompoundIndex()
"""Module-level singleton shared across all adapter classes."""
