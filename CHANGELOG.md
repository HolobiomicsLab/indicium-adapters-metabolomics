# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **`DATA_LICENSES.md`**, also shipped in the wheel as
  `indicium_adapters_metabolomics/data/DATA_LICENSES.md`: source, build date,
  licence and required attribution of every bundled data file (Plant Ontology
  CC BY 4.0, the MIT notice of the NPClassifier labels, Wikidata and RO CC0,
  RefMet under the Metabolomics Workbench terms, UBERON and PubChem).

### Fixed
- The README, the dev guide, the `MetabolomicsAdapter` docstrings and the 0.1.0
  entry below described the compound index as RefMet plus BridgeDb data. No
  bundled file is built from BridgeDb: the index comes from Wikidata, with
  RefMet names and classes for about 3,200 rows. The README licence line now
  points at `DATA_LICENSES.md` instead of asserting a RefMet licence that has
  not been verified.
- `__version__` reads the installed distribution metadata, and CITATION.cff and
  the SECURITY.md support table name 0.8.0, the version in `pyproject.toml`.

## [0.8.0] — 2026-07-10

Lockstep release with `indicium-standard` 2.0.0.

### Changed (breaking)
- **The SHACL shapes now bind `asb:` to `https://w3id.org/asb#`**, following
  indicium 2.0.0's move off the never-registered `asb.holobiomics.org` domain. The shapes
  shipped in 0.7.0 and earlier target the old IRIs, so they silently match nothing against
  claims produced by indicium 2.0.0.
- **Depends on `indicium-standard>=2.0.0`** rather than `indicium>=1.7`. The PyPI name
  `indicium` belongs to an unrelated, abandoned key-value-store package.

## [0.7.0] — 2026-05-24

Feature release closing three deferred items from the v0.6.1 follow-up queue:
GNPS network-view projections, an optional MiniLM matrix-name fuzzy
normaliser, and a 10× expansion of the tier-2 PubChem synonym layer.

### Added
- **`parse_gnps_clusters` / `fetch_gnps_clusters`** (GNPS
  `view_all_clusters_withID_beta`). Projects each cluster row to a
  `has_feature` claim with `subject=gnps_task:<id>`,
  `object=gnps_task:<id>:scan:<cluster_index>`, evidence carrying
  `parent_mass`, `precursor_mz`, `rt_mean`, `rt_stderr`,
  `precursor_charge`, `num_spectra`, `component_index`,
  `sum_precursor_intensity`, `num_files`, plus `library_id` / `spectrum_id`
  / `smiles` when the cluster has a library hit.
- **`parse_gnps_network_pairs` / `fetch_gnps_network_pairs`** (GNPS
  `view_network_pairs`). Projects each MN edge to a `structurally_related_to`
  claim (MetaboKGAdapter vocab — re-used since the qualifier already exists
  and semantically fits cosine-edge similarity). Edges are *undirected* and
  canonicalised numerically (`subject<object`) so a downstream graph sees
  each pair exactly once. Evidence carries `cos_score` and `mz_diff`.
- **`gnps_task_to_claims(..., views=(...))`** — new `views` kwarg lets
  callers opt in to the new (potentially large) clusters / pairs views.
  Defaults preserve v0.6.x behavior (`("annotations","parameters")`).
- **Optional `[ml]` install extra + `_matrix_normalizer` module** — a
  MiniLM-based (`sentence-transformers/all-MiniLM-L6-v2`) fuzzy normaliser
  that maps free-text biological-matrix labels (e.g. `"stool"`, `"leaves"`,
  `"blood plasma"`) to UBERON / PO CURIEs from the curated seed list at
  `data/_uberon_terms.json` (~55 terms, biofluid- and metabolomics-focused).
  Opt in by installing with `pip install indicium-adapters-metabolomics[ml]`
  and passing `normalize_matrix=True` to `redu_to_claims` /
  `redu_sample_to_claims`. On a confident hit (cosine ≥ 0.55), the resolved
  CURIE lands in `ontology_terms.object` and the score in
  `evidence['matrix_match_score']`. The literal object is preserved for
  traceability. Default behavior is unchanged when the flag is False or the
  extra is missing — no silent enrichment, no exception.
- **PROBE_NAMES extended** from 9 to ~80 priority misses across HMDB
  blood/urine biomarkers, gut metabolomics + bile acids, NP / polyphenol
  spelling variants, antibiotic classes, statin/NSAID family, terpenes, and
  carotenoids. The bundled `_synonyms_tier2.json` grew from **9 to 89
  entries** (∼10× expansion). Note: PubChem's default CID for "DCA"
  resolves to dichloroacetic acid, not deoxycholic acid — disambiguated
  via the explicit acronym key in the tier-1 file if you need the bile acid.

### Changed
- **`build_synonyms.py` no longer short-circuits via `COMPOUND_INDEX`** —
  the previous guard `if COMPOUND_INDEX.lookup(name): continue` broke
  incremental re-runs: once a probe landed in `_synonyms_tier2.json` the
  next harvest skipped it and the rebuilt tier-2 file lost the entry. The
  harvester is now fully re-derivable from PROBE_NAMES + cache. Tier-1
  hand-curated aliases still win at load time (CompoundIndex setdefault).

## [0.6.1] — 2026-05-24

Patch release driven by an end-to-end live-endpoint smoke test of the v0.6.0
backends against three real public datasets (GNPS task
`1ad7bc366aef45ce81d2dfcca0a9a5e7`, ReDU MSV000079777, GNPS2 datasetcache
MSV000082048). All findings were closed in this release.

### Changed
- **`datasetcache_row_to_claims` now splits semicolon-multivalue fields**
  into one claim per value (BREAKING for downstream consumers that relied on
  the joined literal). `MassAnalyzer="orbitrap;quadrupole"` now yields TWO
  `uses_mass_analyzer` claims (`orbitrap`, `quadrupole`); `Ionization=
  "electrospray inlet;electrospray ionization"` yields TWO `acquired_in_mode`
  claims. Case-insensitive dedup; whitespace tolerated. The MSV000082048 row
  in the test fixture goes from 3 → 5 claims as a result.
- **`parse_gnps_parameters` no longer emits a standalone `analyzed_with`
  claim** carrying a concatenated tolerance literal (BREAKING for downstream
  consumers reading that claim). Tolerances and thresholds (PM_tolerance,
  Ion_tolerance, MIN_MATCHED_PEAKS, SCORE_THRESHOLD, PAIRS_MIN_COSINE) now
  live as structured keys in the `evidence` dict on `has_processing_software`
  — far easier to use downstream. The `analyzed_with` qualifier is now
  reserved for actual instruments (sourced from datasetcache / ReDU /
  mzTab), matching its definition.

### Added
- **`redu.list_redu_msvs()`** — caches a one-shot fetch of the GH Contents API
  listing of `Wang-Bioinformatics-Lab/ReDU_metadata/main/metadata/` so
  bulk pipelines can skip MSVs known to be missing from the snapshot (saves
  one 404 per file). The snapshot is curated and partial (~292 MSVs at the
  time of release, biased toward older deposits); the new docstring on
  `redu_lookup` explains this and points at the datasetcache fallback for
  MS-operational metadata on newer deposits.
- **Tier-2 PubChem synonym layer** — `data/_synonyms_tier2.json` (9 entries)
  harvested via `data/build_synonyms.py` (PubChem PUG-REST). Closes the 9
  residual misses from audit-2's `domain_probes`: epicatechin acronyms,
  quercetin/kaempferol glycosides (→ isoquercetin / astragalin),
  salinosporamide A → marizomib, equol, acetate. Loaded by
  `CompoundIndex._load()` after tier 1 so the hand-curated tier remains
  authoritative on alias collision. Test
  `test_synonym_layer_v0_6_1_pubchem_tier2` is the new harness for tier-2
  drift checks.

### Fixed
- Docstring on `datasetcache_row_to_claims` now explicitly notes that
  `instrument_model` can be empty on the per-file `uniquemri` row even when
  the dataset-level metadata lists a concrete model; documents the
  fall-back ladder (ReDU `MassSpectrometer` → MetaboLights landing page).

## [0.6.0] — 2026-05-24

Lands four external-data integrations: a ReDU per-MSV metadata lookup, the
two GNPS ProteoSAFe endpoints (`result_json.jsp` annotations + ManageParameters
XML), and the GNPS2 datasetcache datasette for MS-operational metadata. Each
new submodule projects directly into existing adapter qualifier vocab — no
new qualifiers needed.

### Added
- **`indicium_adapters_metabolomics.redu`** — projects per-MSV biological
  sample metadata to existing adapter qualifiers: `found_in_organism`
  (NCBITaxon CURIE; `<id>|<label>` pipe form auto-stripped),
  `acquired_from_matrix` (UBERON CURIE or free-text SampleType fallback),
  `is_biomarker_for` (DOID CURIE), and (for the legacy ReDU `/filename` JSON
  schema only) `analyzed_with`, `acquired_in_mode`, `chromatographed_on`.

  **Backend: GitHub-raw TSVs at `Wang-Bioinformatics-Lab/ReDU_metadata/
  main/metadata/<MSV>.tsv`.** Chose this over the live `redu.ucsd.edu/
  filename` endpoint because the live endpoint was returning 503 at parse
  time; the GH-hosted snapshot is versioned, mirrored, and per-dataset so
  one fetch caches metadata for every scan in a study. Per-MSV TSV is
  cached on disk under `~/.cache/indicium-adapters-metabolomics/redu/
  <MSV>.tsv`; subsequent file-row lookups in the same MSV are pure-Python.

  The projection helper `redu_sample_to_claims` tolerates **both** the GH-TSV
  schema (MassiveID/filename/NCBITaxonomy/UBERONBodyPartName/…) and the
  legacy `/filename` ATTRIBUTE_-prefixed schema, so a future live-endpoint
  revival can be slotted in as a second backend without touching consumers.
- **`indicium_adapters_metabolomics.gnps.datasetcache`** — new module hitting
  `https://datasetcache.gnps2.org/datasette/database/uniquemri.json` for
  MS-operational metadata that ReDU doesn't carry (auto-extracted from
  spectra: MassAnalyzer, Ionization, instrument model/vendor, classification
  e.g. DDA/DIA). Maps to `analyzed_with` (instrument model; vendor folded
  into evidence), `uses_mass_analyzer` (v0.4.0 qualifier — first concrete
  data source), `acquired_in_mode` (Ionization string), and a defensive
  `acquired_from_matrix` only when `sample_type` is a real matrix word (not
  operational tags like 'GNPS'/'MASSIVE-KCF'). Re-exported as
  `datasetcache_to_claims` at package top-level. **Closes the original
  ReDU-503 problem with a complementary data source** — the two together
  give richer coverage than the ReDU `/filename` endpoint did on its own.
- **`indicium_adapters_metabolomics.gnps`** — two parsers sharing infra:
  - `parse_gnps_annotations(blockdata, task_id)` / `fetch_gnps_annotations(task_id)`
    consume `result_json.jsp?view=view_all_annotations_DB`. Emits
    `spectral_match` (MetaboKG) claims with subject
    `gnps_task:<task>:scan:<#Scan#>`, USI in `ontology_terms.object`, and
    MQScore/SharedPeaks/MZErrorPPM/precursor_mz/library/etc. in `evidence`.
  - `parse_gnps_parameters(xml_text, task_id)` / `fetch_gnps_parameters(task_id)`
    consume the ManageParameters XML. Emits `has_processing_software`
    (workflow ID → human label via the v0.5.0 software registry,
    e.g. `METABOLOMICS-SNETS-V2` → `GNPS Classical Molecular Networking`),
    `analyzed_with` (tolerances concatenated literal), `acquired_in_mode`
    (lowercased polarity literal).
  - `gnps_task_to_claims(task_id, *, annotations_data=None,
    parameters_xml=None, …)` — one call for both projections.
- **Live-API smoke tests** for both submodules, gated on the env var
  `INDICIUM_LIVE_TESTS=1` so CI doesn't depend on the live endpoints.

### Tests
- 261 passing on Py 3.13 at 95.53% coverage (was 175 at 99.36%).
- New `tests/test_redu.py` (36 cases), `tests/test_gnps.py` (29 cases),
  `tests/test_datasetcache.py` (20 cases).
- Offline fixtures at:
  - `tests/fixtures/redu_msv_metadata.tsv` — GH-TSV schema (primary path)
  - `tests/fixtures/redu_sample_response.json` — legacy `/filename` JSON
    (covers the ATTRIBUTE_-prefixed schema branch)
  - `tests/fixtures/gnps_annotations_response.json` — trimmed from live
    probe of task `1ad7bc366aef45ce81d2dfcca0a9a5e7`
  - `tests/fixtures/gnps_parameters_response.xml` — verbatim from same probe
  - `tests/fixtures/gnps2_datasetcache_uniquemri.json` — verbatim from
    live probe of `dataset=MSV000082048`
- Live smoke tests for all three HTTP layers are gated on
  `INDICIUM_LIVE_TESTS=1` so CI doesn't depend on the external endpoints.

### Deferred to v0.7.0
- GNPS `view_all_clusters_withID_beta` and `view_network_pairs` views —
  scoped out of this sprint because their column layouts weren't probed
  live; would have meant guessing names. Documented in ROADMAP.
- MiniLM matrix-name fuzzy normaliser — design unchanged from v0.5.0
  ROADMAP. May not be needed if ReDU coverage on a real corpus is high
  enough.
- PubChem tier-2 synonyms — still user-driven via the v0.5.0
  `data/build_synonyms.py` skeleton.

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
- `MetabolomicsAdapter` (8 qualifiers, 10 prefixes, compound enrichment from the bundled stub table).
- `MetaboKGAdapter` (7 qualifiers, 8 prefixes, NPC pathway / annotation level / USI enrichment).
- `EMIAdapter` (13 qualifiers, 15 prefixes, Wikidata QID / plant part / interaction type enrichment).
- Bundled `refmet_compounds.tsv` (stub of 10 metabolites; expand via `build_data.py` in future releases).
- SHACL shapes for `asb:Claim` validation per adapter.
- Entry-point registration under `indicium.adapters` for all three adapters.

### Migration
- Replaces the `MetabolomicsAdapter` previously shipped in `indicium-adapters 0.3.x`.
  Update consumers by installing this package and bumping `indicium-adapters` to `>=0.4.0`.
