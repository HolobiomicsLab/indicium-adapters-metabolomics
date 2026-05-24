# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0] — 2026-05-24

Audit-2 follow-up. A second live audit (3 fresh ASB heuristic builds: Haffner
gut metabolomics, Jeong plant phenolic glycosides, Helena actinomycete natural
products) validated v0.4.0 (5 new qualifiers project 26 real claims; SHACL
teeth catch 2/2 broken claims; MSV URL matches ASB output) and surfaced 8 new
limitations. This release lands the deterministic fixes (5 of 7 actionable
items); the two fuzzy/external-API items are deferred with design notes.

### Added
- **3 study/paper-level qualifiers** on `MetabolomicsAdapter`:
  `uses_database`, `acquired_from_matrix`, `consolidates_dataset`.
  Separates ChEBI/HMDB/KEGG (reference databases) from MS-DIAL/MZmine
  (processing software) per audit finding 6b; captures biological matrix
  (urine/serum/feces/leaf) per 6e; captures paper→multi-MSV consolidation
  per 6h. Qualifier count: Metabolomics 13 → 16; composed union 33 → 36.
- **`data/_software_registry.json`** with 35 software canonical-name aliases
  (MS-DIAL/MSDIAL/MS DIAL → MS-DIAL, MZmine/mzmine 3 → MZmine, GNPS/gnps2 →
  GNPS, CSI:FingerID → SIRIUS, …), 36 reference-database names
  (ChEBI/HMDB/KEGG/PubChem/MetaboLights/MassIVE/GNPS-LIBRARIES/…), and 21
  general-purpose names to ignore (Python/R/Jupyter/GitHub/Docker/pandas/…).
  Closes audit findings 6a (canonical software names) and 6c (language /
  runtime / repo-host ignore-list).
- **`_registries.py` helpers re-exported at package top level:**
  - `canonical_software_name(name)` → canonical spelling or None
  - `is_metabolomics_tool(name)` / `is_metabolomics_database(name)` /
    `is_ignored_tool_name(name)` — disjoint bucket classifiers for ASB's
    free-text `tools` lists
  - `accession_to_curie(name)` — bare repository accession → CURIE
    (`ST002320` → `MW:ST002320`, `MSV000088235` → `MSV:MSV000088235`,
    `MTBLS1234` → `MTBLS:MTBLS1234`). Already-prefixed CURIEs pass through
    unchanged. Closes audit finding 6d (caller had to know MW/MSV/MTBLS
    pattern → prefix mapping).
- **12 more verified compound-name synonyms** in `data/_synonyms.json`
  (`TMAO` → `trimethylamine oxide`, `rapamycin` → `sirolimus`, `p-cresol`
  / `4-methylphenol` → `para-cresol`, `p-coumaric acid` → `4-coumaric acid`,
  `compactin` → `mevastatin`, `indoxyl sulphate` / `tetracyclin` /
  `kanamycin` / `catechin` / `indole-3-propionic acid` aliases). All targets
  verified against the bundled TSV at load time.

### Deferred (audit-2 findings, kept open in ROADMAP)
- **Matrix-name fuzzy normalisation** (audit finding tier-2 of 6e — qualifier
  is added, the synonym layer is not). The matrix vocab (urine, serum, plasma,
  feces/stool/fecal, plant leaf, soil, …) has long-tail spellings that benefit
  from semantic similarity rather than another flat JSON. Tracked as v0.6.0
  candidate with a sentence-transformer (e.g. all-MiniLM-L6-v2) over a curated
  canonical-matrix list. Out of scope for v0.5.0 to keep the package
  zero-ML-dependency.
- **Tier-2 compound-synonym expansion via PubChem PUG-REST**. Audit 2 found
  domain-specific resolution drops (gut metabolomics 65%, natural-product
  drugs 76%). The hand-curated `_synonyms.json` won't scale. Tracked as v0.6.0
  candidate using `/compound/name/<name>/synonyms/JSON` and
  `/compound/name/<name>/cids/JSON` from PubChem to bridge to existing TSV
  PubChem CIDs. Will run inside `build_data.py` so the wheel stays offline.

### Tests
- 175 passing on Py 3.13 at 99.36% coverage (was 99 at 99.3%).
- New `tests/test_registries.py` (37 cases) covers all 4 registry helpers.
- New `test_synonym_layer_v0_5_0_domain_specific_aliases` pins the 12
  audit-2-driven aliases.
- `test_composition.py::test_compose_qualifier_union` updated to 36.

## [0.4.0] — 2026-05-24

Closes the three deferred audit findings carried over from v0.3.1.

### Added
- **5 study-level qualifiers** in `MetabolomicsAdapter.qualifiers`:
  `has_processing_software`, `analyzed_with`, `acquired_in_mode`,
  `chromatographed_on`, `uses_mass_analyzer`. These cover the
  `processing_software`, `instrument`, `ionization_mode`,
  `chromatography_type`, and `mass_analyzer` fields ASB's heuristic
  metabolomics pipeline already extracts — previously the adapter had no
  qualifier vocabulary for any of them. `extraction_context()` is updated.
  Qualifier count: Metabolomics 8 → 13; composed union 28 → 33.
- **Compound-name synonym layer** at `data/_synonyms.json` (~30 high-
  confidence entries). Synonyms are aliased into `CompoundIndex._by_name`
  at load time so `lookup()` resolves `"indole-3-acetic acid"`, `"IAA"`,
  `"ATP"`, `"vitamin b12"`, `"EGCG"`, `"acetylsalicylic acid"`, `"DHA"`,
  `"vitamin c"` (→ ascorbic acid), etc. directly to the canonical row.
  Every alias target is verified against the TSV at load time; unknown
  targets are silently skipped (defensive against TSV regeneration).
- **`ClaimRequiredFieldsShape`** in the base SHACL shapes — every
  `asb:Claim` must carry at least one `asb:subject` AND one `asb:qualifier`
  at `sh:Violation`. Lives on `MetabolomicsAdapter.shacl_shapes()` (the
  family base) so the composed graph carries it exactly once.

### Changed
- **`MetabolomicsClaimCurieShape` bumped from `sh:Warning` to `sh:Violation`**
  per audit finding #4. CURIE-format failures on `asb:subject_ontology_term`
  / `asb:object_ontology_term` now flip `conforms` to `False` instead of
  being silently swallowed by the typical `allow_warnings=True` invocation.
  Prefix vocabulary expanded to include the v0.3.1 additions
  (`MW`, `MSV`).
- **SHACL test helper `_claim_graph`** now injects placeholder `asb:subject`
  + `asb:qualifier` by default so per-qualifier shape tests stay focused on
  the rule they're exercising. Pass `inject_defaults=False` to exercise the
  required-fields shape directly.

### Tests
- 99 passing on Py 3.13 at 99.3% coverage (was 92 at 99.6%).

## [0.3.1] — 2026-05-24

### Added
- **`MSV` and `MW` repository prefixes** in `MetabolomicsAdapter.ontology_prefixes`
  (was `MTBLS` only). MassIVE and Metabolomics Workbench Study accessions are
  the dominant `data_accessions` values emitted by ASB's heuristic metabolomics
  pipeline; previously the adapter silently dropped them.
- **CURIE-keyed enrichment**: `CompoundIndex.lookup()` now resolves subjects
  already in CURIE form — `CHEBI:17234`, `HMDB:HMDB0000122`, `KEGG:C00031`,
  `WD:Q37525`, `LIPIDMAPS:LMPK12070051`, `PUBCHEM:5793` all map back to the
  full cross-reference row. Bare-ID columns in the TSV (hmdb, kegg, lipidmaps)
  are auto-prefixed when indexing. `MetabolomicsAdapter.enrich_claim()` thus
  works for LLM extractors that emit CURIEs directly and for mzTab SML rows
  whose `database_identifier` is already a CURIE — previously these returned
  empty `ontology_terms` despite the bundled TSV containing the data.
- **RefMet enrichment grew**: bundled TSV now ships **3,218 rows with
  `refmet_name`** (was 628 at the v0.3.0 tag). Same count for `chemical_class`,
  `super_class`, `pathway`. Achieved by continuing to run the incremental
  `enrich_with_refmet()` cache against the existing TSV without re-fetching
  Wikidata.

### Changed
- **Python floor bumped to `>=3.12`** to match `indicium-adapters>=0.4.0`
  (audit caught: the prior `>=3.10` declaration plus a 3.10/3.11/3.12/3.13 CI
  matrix made CI break on the 3.10 and 3.11 jobs at `pip install` time because
  the transitive dep could not resolve). CI matrix now `3.12 / 3.13`. Ruff
  `target-version` and classifier list updated accordingly.

### Audit notes (see `audit_indicium_meta_2026-05-24` for reproducer)
- Live audit ran 3 fresh ASB heuristic builds (Mauricio 2018, MetaboLights/
  MetaboAnalyst 2024, IIMN/MSV 2021) and piped outputs through the three
  adapters. Compound-name → CHEBI resolution rate: **14/15 (93%)** on a
  common-metabolite list. All 84 prior tests + 8 new audit-driven tests pass
  on 3.13 at 99.6% coverage.
- Open items deferred: SHACL shapes are mostly `sh:Warning` and don't constrain
  the qualifier vocabulary; no qualifier for `processing_software` /
  `instrument` / `ionization_mode` / `chromatography_type` /
  `mass_analyzer` — five ASB extraction categories the adapter still can't
  represent. Listed in ROADMAP under v0.4.0.

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
