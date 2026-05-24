"""Offline maintainer script — extend _synonyms.json with PubChem PUG-REST.

Status: SKELETON for v0.6.0 (audit-2 finding #7, deferred from v0.5.0).
The user volunteered to drive this. The skeleton wires up the file layout,
cache, throttling, and the existing CompoundIndex round-trip so the only thing
left is the priority list of probe-names and the merge policy.

DO NOT run at install or import time. Run manually before a release:

    python -m indicium_adapters_metabolomics.data.build_synonyms

Why this script exists
======================
The hand-curated `_synonyms.json` (53 entries after v0.5.0) covers vitamins,
acronyms, and a hand-picked audit-driven tier. Coverage on domain-specific
compound classes is still uneven — audit-2 measured 65% (gut metabolomics),
71% (phenolics), 76% (natural-product antibiotics). Manual curation has hit
diminishing returns.

PubChem PUG-REST gives us a deterministic, license-clean way to expand:

  GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/<name>/synonyms/JSON
  GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/<name>/cids/JSON

For each missing probe-name we look it up by PubChem CID, then bridge back
through the bundled TSV's `pubchem` column to find the canonical row already
in the index. The resulting (alias, canonical) pair joins the synonym layer
exactly like the hand-curated entries do — same load-time verification, same
silent-skip on TSV drift.

Output strategy
===============
- Writes to `_synonyms_tier2.json` (a NEW file, not merged into
  `_synonyms.json`) so the hand-curated tier stays human-reviewable.
- `_enrichment.py::CompoundIndex._load()` will need a one-line addition to
  load `_synonyms_tier2.json` after the tier-1 file (drop the addition in
  the same PR as the first run of this script).
- Caches every PubChem call to `_pubchem_synonyms_cache.json` (gitignored,
  add to `.gitignore`) so re-runs are incremental — same pattern as the
  existing `_refmet_cache.json`.

Politeness / rate limits
========================
PubChem PUG-REST policy: max 5 requests/second, 400 requests/minute,
300 requests/second from a single IP across all NCBI services. Throttle at
0.25s/request (4 rps headroom).

What's left for the maintainer
==============================
1. Define `PROBE_NAMES` — the priority misses to look up. Easiest first pass:
   collect compound names from a recent ASB heuristic run and filter to those
   that `COMPOUND_INDEX.lookup()` returns None for. Audit-2's three
   `domain_probes` blocks in `/tmp/audit2_adapter.py` are a good seed.
2. Decide the merge policy: alias-from-PubChem → which-PubChem-row → canonical
   TSV name. The default in `_canonical_from_cid()` below is "first
   PubChem-CID hit, lookup its row in the index, use that row's name_lower."
3. Optionally add a tier-2 SHACL/test for the new aliases (the existing
   `test_synonym_layer_v0_5_0_domain_specific_aliases` is the template).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from indicium_adapters_metabolomics._enrichment import COMPOUND_INDEX

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name"
USER_AGENT = (
    "indicium-adapters-metabolomics/0.6.0-dev build_synonyms.py "
    "(https://github.com/HolobiomicsLab/indicium-adapters-metabolomics)"
)
SLEEP_S = 0.25  # 4 rps, well under the 5 rps PubChem limit

DATA_DIR = Path(__file__).parent
OUTPUT_PATH = DATA_DIR / "_synonyms_tier2.json"
CACHE_PATH = DATA_DIR / "_pubchem_synonyms_cache.json"   # gitignored

# Pre-seeded from the 9 residual misses of audit-2's `domain_probes` after
# v0.5.0 synonyms landed. Maintainer should extend this list — likely from
# Perspicacite-AI / Scriptorium claim-extraction runs whose subjects fail
# COMPOUND_INDEX.lookup(). Each probe-name is something a paper, an LLM, or
# a tool exports as a compound label that the bundled TSV does not match
# under any current alias.
PROBE_NAMES: list[str] = [
    # Audit-2 residual misses (verified missing on 2026-05-24 against the
    # v0.5.0 index, after tier-1 _synonyms.json applied):
    "(-)-epicatechin",
    "acetate",
    "epicatechin",
    "equol",
    "kaempferol 3-O-glucoside",
    "kaempferol-3-glucoside",
    "quercetin 3-O-glucoside",
    "quercetin-3-glucoside",
    "salinosporamide a",
    # Add more here. Suggested sources:
    #   * Recent ASB/Perspicacite-AI metabolomics-paper runs
    #   * MetaboAtlas common-name lists not in Wikidata
    #   * HMDB primary-name lists for blood/urine/CSF biomarkers
]


def _load_cache() -> dict[str, dict]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict[str, dict]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def _pubchem_cids(name: str, sess: requests.Session) -> list[int]:
    """PubChem `/name/<name>/cids/JSON` — returns list[CID] (often 1)."""
    r = sess.get(f"{PUBCHEM}/{requests.utils.quote(name)}/cids/JSON", timeout=15)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return list(r.json().get("IdentifierList", {}).get("CID", []))


def _canonical_from_cid(cid: int) -> str | None:
    """Map a PubChem CID back to a canonical name already in the bundled TSV.

    Uses the existing `_by_curie` index — if the CID exists in the TSV we get
    the row directly; otherwise we don't try to expand the index (the synonym
    layer is for *names already in the TSV under a different label*, not for
    adding new compounds)."""
    row = COMPOUND_INDEX.lookup(f"PUBCHEM:{cid}")
    return row.get("name_lower") if row else None


def harvest(probes: list[str]) -> dict[str, str]:
    """For each probe-name not in the TSV, find its PubChem CID, map back to
    the canonical TSV name, and emit (probe → canonical). Cached + throttled."""
    COMPOUND_INDEX._load()
    cache = _load_cache()
    out: dict[str, str] = {}
    sess = requests.Session()
    sess.headers["User-Agent"] = USER_AGENT
    for name in probes:
        if COMPOUND_INDEX.lookup(name):
            continue  # already resolves; nothing to do
        if name in cache:
            entry = cache[name]
        else:
            try:
                cids = _pubchem_cids(name, sess)
            except requests.RequestException as e:
                print(f"  PubChem error for {name!r}: {e}")
                cids = []
            entry = {"cids": cids}
            cache[name] = entry
            _save_cache(cache)
            time.sleep(SLEEP_S)
        for cid in entry.get("cids", []):
            canonical = _canonical_from_cid(cid)
            if canonical:
                out[name] = canonical
                break
    return out


def main() -> None:
    if not PROBE_NAMES:
        raise SystemExit(
            "PROBE_NAMES is empty — populate it with the misses you want to "
            "close, then re-run. See module docstring."
        )
    aliases = harvest(PROBE_NAMES)
    payload = {
        "_meta": {
            "description": "Tier-2 compound-name synonyms harvested via PubChem PUG-REST. "
                           "Loaded after _synonyms.json. Targets are canonical names "
                           "already present in refmet_compounds.tsv.",
            "version": 1,
            "source": "PubChem PUG-REST /compound/name/<n>/cids/JSON",
        },
        **dict(sorted(aliases.items())),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"  wrote {len(aliases)} aliases to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
