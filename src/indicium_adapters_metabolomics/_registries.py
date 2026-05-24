"""Lightweight registries shared by the metabolomics adapter family.

Two responsibilities:

1. **Software / database / ignore registry** (audit-2 findings 6a/6b/6c).
   ASB's heuristic `tools` list is free-text — it emits 'MS-DIAL', 'MSDIAL'
   and 'MS DIAL' interchangeably, mixes processing software with reference
   databases ('ChEBI', 'HMDB'), and includes general-purpose languages and
   repo hosts ('Python', 'R', 'GitHub'). Without normalisation downstream
   consumers can't tell whether `(study, has_processing_software, 'MS-DIAL')`
   and `(study, has_processing_software, 'msdial')` refer to the same tool.

   * `canonical_software_name(name)` → canonical spelling or None.
   * `is_metabolomics_tool(name)` → True iff registered as software.
   * `is_metabolomics_database(name)` → True iff registered as a database.
   * `is_ignored_tool_name(name)` → True iff the name is a generic
     language/runtime/repo-host that should never enter a claim.

   The registry is loaded lazily from `data/_software_registry.json`.

2. **Accession-prefix helper** (audit-2 finding 6d). ASB's heuristic
   `data_accessions` list emits bare repository accessions ('ST002320',
   'MSV000088235', 'MTBLS1234'). The adapter's prefix map carries CURIE
   templates for `MW`, `MSV`, and `MTBLS` — but the adapter never auto-
   prepends them so consumers have to know the mapping. `accession_to_curie()`
   centralises that: 'ST002320' → 'MW:ST002320', 'MSV000088235' →
   'MSV:MSV000088235', 'MTBLS1234' → 'MTBLS:MTBLS1234'. Already-prefixed
   accessions pass through unchanged.
"""
from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Final

# --- 1. Software / database / ignore registry -----------------------------

_REGISTRY: dict[str, object] | None = None


def _load_registry() -> dict[str, object]:
    """Lazy-load the JSON registry once per process."""
    global _REGISTRY
    if _REGISTRY is None:
        path = files("indicium_adapters_metabolomics.data").joinpath(
            "_software_registry.json"
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        # Pre-compute case-folded lookup maps for O(1) probes.
        software_map: dict[str, str] = data.get("software", {})
        software_canonicals: set[str] = set(software_map.values())
        _REGISTRY = {
            "software_map": {k.lower(): v for k, v in software_map.items()}
            | {v.lower(): v for v in software_canonicals},
            "software_canonicals": software_canonicals,
            "databases": {d.lower() for d in data.get("databases", [])},
            "ignore": {x.lower() for x in data.get("ignore", [])},
        }
    return _REGISTRY


def canonical_software_name(name: str) -> str | None:
    """Map a free-text tool name to its canonical spelling, or None.

    Case-insensitive. Whitespace-tolerant. Returns the spelling stored in
    `_software_registry.json` (e.g. 'MS-DIAL', 'MZmine', 'GNPS')."""
    if not name or not name.strip():
        return None
    reg = _load_registry()
    return reg["software_map"].get(name.strip().lower())  # type: ignore[union-attr]


def is_metabolomics_tool(name: str) -> bool:
    """True iff `name` is a registered processing-software name (any alias)."""
    return canonical_software_name(name) is not None


def is_metabolomics_database(name: str) -> bool:
    """True iff `name` is one of the curated reference-database names.

    Used by bridge layers to project (study, uses_database, <db>) instead of
    (study, has_processing_software, <db>) for things like 'ChEBI'/'HMDB'."""
    if not name or not name.strip():
        return False
    reg = _load_registry()
    return name.strip().lower() in reg["databases"]  # type: ignore[union-attr]


def is_ignored_tool_name(name: str) -> bool:
    """True iff `name` is a general-purpose language/runtime/repo host that
    should NEVER enter a metabolomics claim (Python, R, Jupyter, GitHub, …).

    Bridge layers should drop these before emitting any claim."""
    if not name or not name.strip():
        return False
    reg = _load_registry()
    return name.strip().lower() in reg["ignore"]  # type: ignore[union-attr]


# --- 2. Accession-prefix helper -------------------------------------------

# Bare-accession patterns observed in ASB heuristic output. Anchored at start.
# Order matters: more-specific patterns first.
_ACCESSION_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    # Metabolomics Workbench Study accessions: ST followed by 5+ digits.
    (re.compile(r"^ST\d{5,}$", re.I),       "MW"),
    # MassIVE: MSV followed by 9 digits.
    (re.compile(r"^MSV\d{9}$", re.I),       "MSV"),
    # MetaboLights: MTBLS followed by 1+ digits.
    (re.compile(r"^MTBLS\d+$", re.I),       "MTBLS"),
)


def accession_to_curie(accession: str) -> str | None:
    """Normalise a bare metabolomics-repository accession to a CURIE.

    Recognises Metabolomics Workbench Study (`ST######` → `MW:ST######`),
    MassIVE (`MSV#########` → `MSV:MSV#########`) and MetaboLights
    (`MTBLS####` → `MTBLS:MTBLS####`). Already-prefixed CURIEs (containing
    a `:`) are returned unchanged so callers can pipe both bare and CURIE
    forms through the same helper. Unknown patterns return None — the
    caller decides whether to keep the raw string or drop the value.

    Added in v0.5.0 per audit-2 finding 6d.
    """
    if not accession or not accession.strip():
        return None
    a = accession.strip()
    if ":" in a:  # already a CURIE
        return a
    for pat, prefix in _ACCESSION_PATTERNS:
        if pat.match(a):
            return f"{prefix}:{a.upper()}"
    return None
