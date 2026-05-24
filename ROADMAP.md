# Roadmap

Items explicitly out of scope for v0.1.0, kept here for future minor releases.

## v0.2.0 — RELEASED 2026-05-24

See CHANGELOG.md.

## v0.3.0 — RELEASED 2026-05-24

See CHANGELOG.md.

Done items from the v0.3.0 candidate list:
- **RefMet canonical-name layer**: `refmet_name` populated for 628 rows via
  per-InChIKey REST API (throttled, cached, gitignored cache). Fills
  `chemical_class`, `super_class`, `pathway` too. v0.3.0 was a partial run
  (cap 5,000 priority rows; 900 looked up so far); re-run `build_data.py`
  to extend coverage incrementally via the cache.
- **Wikidata top-organisms sitelink ranking**: 53-species curated lookup (via
  P225 taxon name, two batches) + broad P31=Q16521 LIMIT 400 supplement.
  460 organisms with canonical QIDs.

## v0.4.0 candidates

- **mzTab-M SME (evidence) projection** — extend `parse_mztab_to_claims` to
  also emit `spectral_match` claims from SME rows.
- **Compress the bundled TSV** — gzip dropping ~22 MB to ~5 MB; CompoundIndex
  loads transparently.
- **Expand RefMet enrichment** — cover the remaining ~16k rows that have
  InChIKey + HMDB but not KEGG/PubChem.

## v0.5.0+ — paper-workflow expansion

A coordinated theme: make `indicium-adapters-metabolomics` cover an entire
untargeted-metabolomics paper end-to-end (LLM-extracted claims + tool outputs
+ compound resolution + reference DB enrichment), so claims from prose and
claims from instruments/pipelines feed into the same Scriptorium graph.

### Tool-output parsers (one file/dir → list[asb:Claim])

Same pattern as the existing `indicium_adapters_metabolomics.mztab.parse_mztab_to_claims()`.
Each ships as its own submodule.

- **`sirius`** — SIRIUS 5/6 project dirs. Read `compound_identifications.tsv`,
  `structure_candidates.tsv`, `canopus_compound_summary.tsv`,
  `formula_identifications.tsv`. Emits `identifies`, `has_molecular_formula`,
  `classified_as` (NPC + ClassyFire predictions), `has_csi_score`,
  `has_canopus_class`, `has_zodiac_score`. **High priority** — most-used
  annotation tool in the GNPS/MetaboKG ecosystem.
- **`matchms`** — accepts a `matchms.Scores` object (or its JSON serialization
  / pickle), or a list of `matchms.Spectrum`. Projects pairwise similarity
  results into `spectral_match` claims with score-type metadata
  (cosine / modified-cosine / Spec2Vec / MS2DeepScore / MS2Query). Also surfaces
  per-spectrum metadata as `has_inchikey`, `has_smiles`, `has_precursor_mz`
  claims. **High priority** — matchms underlies MS2Query, MZmine's library
  match, and most modern Spec2Vec / MS2DeepScore workflows.
- **`gnps`** — GNPS / GNPS2 FBMN task results. Given a task UUID, fetch
  `clusterinfosummarygroup_attributes_withIDs/...tsv` and
  `result_specnets_DB/...tsv` from the public API. Emits `spectral_match`
  (library hits with cosine + shared peaks), `co_occurs_with` (network edges),
  `annotated_in` (task UUID provenance), `has_classyfire_class`. **High priority.**
- **`mzmine`** — MZmine 3/4 feature-table CSV + MGF + IIN (ion-identity network)
  edges. Emits `has_feature`, `coelutes_with`, `is_adduct_of`, `is_isotope_of`,
  `has_retention_time`, `has_exact_mass`. **High priority.**
- **`msdial`** — MS-DIAL `*_Height.txt` / `*_Area.txt` exports. Same claim
  shape as the mzmine parser (just a different format). Medium priority.
- **`metfrag`** — MetFrag in-silico fragmentation CSVs. Emits `spectral_match`
  with `MetFragScore` evidence. Medium priority.
- **`mona`** — MoNA `.msp` library files. Emits `has_reference_spectrum` and
  compound metadata. Medium priority.

### Compound-name resolution (`MetabolomicsAdapter` enrichment upgrade)

Today `enrich_claim()` matches only exact lowercased names. Real papers use
"β-D-glucose", "G6P", "PC 36:4", "vitamin C", etc. New `resolve_compound(name)`
helper that tries in priority order:

1. **Bundled static index** (current ~156k Wikidata names)
2. **Bundled synonym index** — new `build_synonyms.py` script extracting
   `skos:altLabel` + ChEBI synonyms; ship as `_synonyms.json`
3. **`pygoslin`** — lipid shorthand parser (e.g. "PC 36:4" → LIPIDMAPS class).
   Optional `[lipids]` extra.
4. **`py2opsin`** — IUPAC nomenclature → SMILES → InChIKey. Optional `[opsin]` extra.
5. **PubChem PUG REST** — fuzzy name → CID. Optional `[live]` extra with disk cache.
6. **Chemical Translation Service (CTS)** — bulk multi-DB resolution. Same
   `[live]` extra.

Plus an optional `[rdkit]` extra for SMILES canonicalization + InChIKey
generation when the input has SMILES but no key.

### New qualifiers

| Qualifier | Slot expectations | Adapter |
|-----------|-------------------|---------|
| `has_molecular_formula` | object = Hill-notation formula string | MetabolomicsAdapter |
| `has_inchikey` | object = 27-char or 14-char InChIKey | MetabolomicsAdapter |
| `has_smiles` | object = SMILES string | MetabolomicsAdapter |
| `has_exact_mass` | object = m/z literal | MetabolomicsAdapter |
| `has_retention_time` | object = seconds literal | MetabolomicsAdapter |
| `is_adduct_of` | both slots = feature IDs | MetaboKGAdapter |
| `is_isotope_of` | both slots = feature IDs | MetaboKGAdapter |
| `coelutes_with` | both slots = feature IDs | MetaboKGAdapter |
| `has_csi_score` | object = float literal | MetaboKGAdapter (or new SIRIUS adapter) |
| `has_canopus_class` | object = NPC: CURIE | MetaboKGAdapter |
| `has_zodiac_score` | object = float literal | MetaboKGAdapter |
| `has_similarity_score` | object = float literal; needs evidence_type qualifier sub-field for cosine/Spec2Vec/MS2DeepScore | MetaboKGAdapter |
| `correlates_with` | both slots = metabolite names; statistical claim | MetabolomicsAdapter |
| `upregulated_in` | object = condition/disease | MetabolomicsAdapter |
| `downregulated_in` | object = condition/disease | MetabolomicsAdapter |
| `derived_from` | object = parent compound; biosynthetic claim | MetabolomicsAdapter |
| `has_reference_spectrum` | object = USI or library accession | MetaboKGAdapter |

`test_composition.test_qualifiers_are_disjoint_across_adapters` must continue
to hold — each qualifier owned by exactly one adapter.

### Reference databases worth bundling

| Dataset | Use | Size budget |
|---------|-----|-------------|
| **HMDB compact TSV export** | Human-metabolome biofluid + disease links | ~10 MB |
| **LIPID MAPS LMSD subset** | Lipid class hierarchy (LMID → category → main/sub) | ~5 MB |
| **DOID + MONDO subset** | Map disease names → DOID/MONDO CURIEs for `is_biomarker_for` | ~2 MB |
| **EFO subset** | Experimental factors for `discriminates_between` | ~3 MB |
| **MoNA InChIKey index** | "Was this spectrum seen before?" — probably its own `indicium-adapters-spectra` package | ~50 MB |

### Source materials needed from a user

To scaffold each tool-output parser via TDD, the maintainer needs a small
representative output:

- **SIRIUS** — one project dir (`.sirius` zip OK), with the version that produced it
- **MZmine** — one `_quant_full.csv` + the associated `.mgf` for a tiny experiment
- **GNPS / GNPS2** — a task UUID (the parser fetches results from the public API)
- **matchms** — a `Scores` object pickle + the input `Spectrum` list (or their JSON serialization)
- **MS-DIAL** — one `*_Height.txt` export
- **MetFrag** — one `*-MetFrag.csv`
- **MoNA** — one small `.msp`

Per parser: `feat/<tool>-parser` branch → TDD against the fixture → ship as
new submodule + new qualifiers + tests + CHANGELOG.

## Future / v0.6.0+ candidates

- **`[enrichment]` optional extra** for live ChEBI / PubChem REST lookup with
  on-disk caching (separate from the `[live]` extra in §v0.5.0+; this one is
  for filling gaps in the bundled compound index without depending on the
  paper-workflow parsers).
- **`query_claims(question)` Protocol extension** for KG-backed SPARQL
  adapters (requires bumping `indicium-adapters.CURRENT_API_VERSION` to 2;
  coordinated release across consumers).
- **Live MetaboKG SPARQL endpoint adapter** once an endpoint URL stabilizes.
- **Sibling packages**: `indicium-adapters-lipidomics` (ChEMBL + LIPID MAPS
  hierarchy as a focused package), `indicium-adapters-proteomics`,
  `indicium-adapters-spectra` (MoNA / MassBank libraries).
