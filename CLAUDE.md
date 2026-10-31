# CLAUDE.md — Dev Guide

## Read this before adding anything

The package's design philosophy and the 4-quadrant filter for new features
live at the top of `ROADMAP.md` ("Design philosophy — why this package exists
in the age of agentic AI"). Any new contribution should justify itself in
those terms: does it **constrain** the agent, **resolve** identifiers,
**validate** output, or is it something an agent could do as well freehand?
If the last, skip it.

## Project shape

Three sibling `DomainAdapter` classes in one wheel:

- `MetabolomicsAdapter` (base) — generic MS/NMR claims, Wikidata+RefMet enrichment
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
5. If it needs validation, add a NodeShape in the adapter's shapes TTL. Key any
   per-qualifier rule on `asb:domainQualifier "<term>"`, NOT `asb:qualifier` —
   Perspicacité routes domain qualifiers to the open `asb:domainQualifier` slot
   (indicium#1 / indicium 1.7.0); the closed `asb:qualifier` only carries Bucur
   SuperPattern terms.
6. Add unit tests in `tests/test_<adapter>.py`.
7. `test_composition.py` asserts qualifier sets are disjoint across adapters — keep it that way.

## Refreshing bundled data files

Two maintainer-only scripts under `src/indicium_adapters_metabolomics/data/`:

- `build_data.py` regenerates `refmet_compounds.tsv` from the Wikidata SPARQL
  endpoint. Chunked by ChEBI ID range with checkpoint resume. After the
  Wikidata fetch, calls `enrich_with_refmet()` which hits the Metabolomics
  Workbench REST API for the 5k highest-priority rows (InChIKey + HMDB + KEGG/
  PubChem). Caches to `_refmet_cache.json` (gitignored). Run with:

      python -m indicium_adapters_metabolomics.data.build_data

  To re-enrich only (without re-fetching Wikidata), load the existing TSV and
  call `enrich_with_refmet()` directly (see sprint notes for the one-off
  invocation pattern).

- `build_vocabs.py` regenerates the 4 inline-vocab JSON files
  (`_npc_terms.json`, `_po_terms.json`, `_ro_terms.json`, `_wd_organisms.json`)
  from npc_taxonomy.ttl (local), PO/RO OWL (downloaded), Wikidata SPARQL:

      python -m indicium_adapters_metabolomics.data.build_vocabs

  The `_wd_organisms.json` file now uses a two-tier strategy: curated P225
  taxon-name lookup (53 species, 2 batches) + broad P31=Q16521 LIMIT 400.
  This avoids the 60s WQS timeout that killed ORDER-BY approaches.

Don't run either at install or import time.

## The mztab submodule

`indicium_adapters_metabolomics.mztab.parse_mztab_to_claims(path)` reads a PSI
mzTab-M 2.0 file and projects:
- SML (small-molecule summary) rows → `identifies` claims (subject=chemical_name,
  object=database_identifier, ontology_terms populated if the database_identifier
  is a CURIE).
- SMF (small-molecule feature) rows → `has_feature` claims.

SME (evidence) projection is on the v0.3.0 roadmap.

## Test before commit

```bash
ruff check .
pytest --cov=indicium_adapters_metabolomics
```

CI matrix is 3.12 / 3.13. `indicium-adapters>=0.4.0` requires `>=3.12`, so the
metabolomics package's floor follows it.

## Repo relationships

- Core Protocol lives in `~/git/indicium-adapters` (do not vendor it).
- The previous `MetabolomicsAdapter` was removed from core in `indicium-adapters 0.4.0`.
- Pipeline RDF validation (MBS:, emi: classes) stays in `~/git/metabokg/shapes/` and `~/git/earth_metabolome_ontology/` — we do not duplicate it here.
