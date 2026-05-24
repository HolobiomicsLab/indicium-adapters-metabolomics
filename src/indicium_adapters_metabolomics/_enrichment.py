"""CompoundIndex — lazy in-memory lookup for metabolite name/InChIKey → cross-references.

Loads `data/refmet_compounds.tsv` on first lookup. Module-level singleton
`COMPOUND_INDEX` shared across all adapter instances and adapter classes.
Pure function: no I/O during lookup, no network anywhere.
"""
from __future__ import annotations

import csv
from importlib.resources import files


class CompoundIndex:
    """Compound name / InChIKey → cross-reference row lookup.

    Loads lazily on first `.lookup()` call. Returns `None` for unknown queries.
    Rows are dicts with keys matching the TSV column names; downstream code is
    responsible for selecting which CURIE to use (CHEBI / HMDB / PUBCHEM, etc.).
    """

    def __init__(self) -> None:
        self._by_name: dict[str, dict[str, str]] = {}
        self._by_inchikey: dict[str, dict[str, str]] = {}
        self._by_inchikey2d: dict[str, dict[str, str]] = {}
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
        self._loaded = True

    def lookup(self, query: str) -> dict[str, str] | None:
        """Look up a compound by name (case-insensitive), full InChIKey (27 chars),
        or InChIKey2D (14 chars). Returns the matching row dict, or None."""
        if not query or not query.strip():
            return None
        self._load()
        q = query.strip()
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
