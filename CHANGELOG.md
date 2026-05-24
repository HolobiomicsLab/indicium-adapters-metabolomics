# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] — 2026-05-24

### Added
- **RefMet canonical-name layer**: `refmet_name` column in the bundled TSV is
  now populated for 628 rows (was empty in v0.2.0). Built by querying the
  Metabolomics Workbench REST API (`/rest/refmet/match/<inchikey>/all`) for
  rows with an InChIKey AND an HMDB ID AND at least one of KEGG or PubChem
  (cap 5,000 highest-priority rows; v0.3.0 was a partial run that cached
  900 lookups with ~70% RefMet hit rate before being checkpointed).
  Re-running `build_data.py` against the existing cache at
  `data/_refmet_cache.json` (gitignored) is incremental — fills more on
  subsequent invocations without re-fetching. Also fills `chemical_class`
  (RefMet `main_class`), `super_class`, and `pathway` (`sub_class`) where
  available.
- **Wikidata top-organisms ranked by sitelinks**: replaces v0.2.0's random-sample
  list (200 entries, no rank ordering) with a proper curated+ranked query split
  into two tiers to dodge the WQS 60s timeout:
  - Tier A: 53 curated well-known species by scientific name (via `wdt:P225`)
    in two batches — guarantees coverage of Homo sapiens, Apis mellifera,
    Coffea arabica, Arabidopsis thaliana, etc.
  - Tier B: broad `wdt:P31=Q16521` supplement (LIMIT 400, no ORDER BY) for
    additional coverage.
  Result: 460 organisms (was 200); common species now present with canonical
  QIDs.

### Notes
- The RefMet cache at `data/_refmet_cache.json` is gitignored. Re-running
  `build_data.py` reuses the cache; delete it to force a full refresh.
- The enrichment covers ~5k highest-priority rows per run. The remaining
  ~16k rows (InChIKey + HMDB only, no KEGG/PubChem) are roadmap for v0.4.0.

## [0.2.0] — 2026-05-24

### Added
- **Bundled compound TSV expanded from 10-row stub to ~156k rows** via Wikidata
  SPARQL. Covers all ChEBI-mapped compounds with cross-references to HMDB,
  KEGG, LIPIDMAPS, PubChem, Wikidata QID. `build_data.py` is now the
  maintainer-run regeneration script (with checkpoint resume).
- **Inline vocabularies expanded** from 10-entry stubs to full extracts of
  NPClassifier (771 terms from npc_taxonomy.ttl), Plant Ontology body parts
  (1363 terms), Relations Ontology biotic interactions (13 terms), and
  top-200 Wikidata ecological organisms. Stored as
  `data/_npc_terms.json`, `_po_terms.json`, `_ro_terms.json`,
  `_wd_organisms.json`. `build_vocabs.py` regenerates.
- **mzTab-M 2.0 parser submodule** `indicium_adapters_metabolomics.mztab` with
  `parse_mztab_to_claims(path)` that projects SML and SMF sections of an
  `.mztab` file into `asb:Claim` dicts. SME (evidence) is deferred to v0.3.0.
- **Dependencies:** `pyteomics>=4.7`, `requests>=2.31`.

### Changed
- `MetaboKGAdapter`'s NPC enrichment now uses 771 terms (was 10).
- `EMIAdapter`'s plant-part enrichment uses 1363 terms (was 10); interaction-type
  uses 13 (was 10). **New:** organism-label lookup against Wikidata top-200 —
  claims with subject in the bundled list resolve to `WD:Qxxx` directly.
- Test assertions that pinned specific RefMet names now pin CHEBI CURIEs instead,
  since the Wikidata-derived `name_lower` is not RefMet-canonical at v0.2.0.

### Notes
- `name_lower` in the bundled TSV is Wikidata-derived (English label).
  RefMet canonical-name layer is deferred to v0.3.0 (bulk endpoint not yet
  wired up).
- Bundled TSV is 22 MB — large but acceptable for a private package. Future
  releases may compress or filter.
- Wikidata SPARQL for top-organisms was simplified due to a 504 timeout on the
  property-path traversal; the 200 entries are a random sample of Q16521
  (taxon) instances rather than strictly "top by sitelinks."

## [0.1.0] — 2026-05-24

### Added
- Initial release.
- `MetabolomicsAdapter` (8 qualifiers, 10 prefixes, RefMet+BridgeDb compound enrichment).
- `MetaboKGAdapter` (7 qualifiers, 8 prefixes, NPC pathway / annotation level / USI enrichment).
- `EMIAdapter` (13 qualifiers, 15 prefixes, Wikidata QID / plant part / interaction type enrichment).
- Bundled `refmet_compounds.tsv` (stub of 10 metabolites; expand via `build_data.py` in future releases).
- SHACL shapes for `asb:Claim` validation per adapter.
- Entry-point registration under `indicium.adapters` for all three adapters.

### Migration
- Replaces the `MetabolomicsAdapter` previously shipped in `indicium-adapters 0.3.x`.
  Update consumers by installing this package and bumping `indicium-adapters` to `>=0.4.0`.
