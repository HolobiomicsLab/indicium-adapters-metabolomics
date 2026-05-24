# CLAUDE.md — Dev Guide

## Project shape

Three sibling `DomainAdapter` classes in one wheel:

- `MetabolomicsAdapter` (base) — generic MS/NMR claims, RefMet+BridgeDb enrichment
- `MetaboKGAdapter` — MetaboKG/GNPS analysis claims
- `EMIAdapter` — ENPKG + METRIN-KG ecological claims

All three:
- have `api_version = 1` matching `indicium-adapters.CURRENT_API_VERSION`
- implement both `DomainAdapter` and `SHACLProvider` protocols
- are registered under the `indicium.adapters` entry-point group
- use **hardcoded namespace URI constants** in `_namespaces.py` (no runtime dep on metabokg / earth_metabolome_ontology Python packages)

## Adding a new qualifier

1. Decide which of the three adapters owns it (or whether it justifies a 4th).
2. Add to that adapter's `qualifiers` frozenset.
3. Update `extraction_context()` to mention it.
4. If it needs enrichment behavior, add a branch in `enrich_claim()`.
5. If it needs validation, add a NodeShape in the adapter's shapes TTL.
6. Add unit tests in `tests/test_<adapter>.py`.
7. `test_composition.py` asserts qualifier sets are disjoint across adapters — keep it that way.

## Refreshing the bundled compound TSV

`src/indicium_adapters_metabolomics/data/build_data.py` is a maintainer-only script.
Currently a skeleton; wire up the `fetch_*` functions when running a release-time refresh.
Output: `data/refmet_compounds.tsv`. Don't run at install or import.

## Test before commit

```bash
ruff check .
pytest --cov=indicium_adapters_metabolomics
```

CI matrix is 3.10 / 3.11 / 3.12.

## Repo relationships

- Core Protocol lives in `~/git/indicium-adapters` (do not vendor it).
- The previous `MetabolomicsAdapter` was removed from core in `indicium-adapters 0.4.0`.
- Pipeline RDF validation (MBS:, emi: classes) stays in `~/git/metabokg/shapes/` and `~/git/earth_metabolome_ontology/` — we do not duplicate it here.
