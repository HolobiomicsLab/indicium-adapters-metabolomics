# Roadmap

Items explicitly out of scope for v0.1.0, kept here for future minor releases.

---

## Design philosophy — why this package exists in the age of agentic AI

The adapter is best understood as **a tool the agent uses**, not as something
competing with the agent. In an era where LLMs/agents can read papers, parse
file formats, and call REST APIs on demand, the question "why bundle all this
infrastructure?" deserves a clear answer. Future contributions should be
filtered through it.

### What the adapter genuinely provides — and what gets MORE valuable, not less, as agents proliferate

| Contribution | Why it earns its keep |
|--------------|----------------------|
| **Bundled cross-reference TSV** (~156k compounds) | An agent resolving "glucose → CHEBI:17234" via REST is **non-deterministic** (synonyms reshuffle), **slow** (~300ms/call × 10k compounds = an hour), and **hallucinates CURIEs** that don't exist. A disk lookup is ~10µs and reproducible across sessions and years. |
| **`qualifiers` frozensets** | These go **into the LLM's extraction prompt** as a closed vocabulary. Without them, every paper invents its own predicates (`upregulated_in` / `over-expressed-in` / `elevated_among`) and downstream queries can't join across papers. With them, claims from 1000 papers compose into one queryable graph. This is the substrate that makes agent-extracted claims aggregate-useful, not just per-paper-useful. |
| **Cross-property SHACL constraints** (the meaningful ones, not regex shapes) | `spectral_match` MUST have a USI/InChIKey/CHEBI in object; `mediates_interaction` MUST have a Wikidata Q-id somewhere. These are invariants an extractor agent can't reliably enforce on itself because they're cross-cutting. SHACL is the spell-check that catches the agent's bad days. |
| **Versioned, tested tool-output parsers** (mzTab-M, SIRIUS, MZmine, matchms, GNPS) | A parser written once + tested + tagged at `v0.X.0` is reproducible from a `pip install`. The same job done freehand by an agent each session: 60s of reasoning per invocation, non-deterministic output, no test fixtures, no regression guard. **The agent should be USING the parser, not re-deriving it.** |
| **Determinism for citations** | "Glucose (CHEBI:17234)" in a paper has to mean the same thing in 5 years. If your pipeline asks an LLM for the CURIE every time, you're one model-update away from your citations drifting. |

### What the adapter should NOT keep doing (filter-out criteria)

- **Hand-curated micro-dicts** (the original `_NPC_PATHWAYS = {10 entries}`) — replace with bulk extracts from authoritative sources (`npc_taxonomy.ttl`, Wikidata SPARQL). v0.2.0 already moved in this direction; keep going.
- **CURIE-prefix-regex SHACL shapes** at sh:Warning level — an agent reviewing the claim would catch these; the validation theater isn't worth the maintenance.
- **Anything an agent could do as well freehand** — if it's a one-shot task where the agent has the context and the cost-per-call is negligible, don't crystallize it into code.

### The cost calculation that crystallizes the value

One metabolomics paper through Perspicacite-AI:
- **With adapters:** ~5k LLM tokens (extraction bound by closed vocab) + ~10ms enrichment + SHACL pass. **~$0.01.**
- **Without adapters, agent freehand:** ~50k tokens (extract, reason about ontology, call REST APIs, validate, retry hallucinations) + ~30 REST calls. **~$0.15.**

At 1 paper, 15× cost is invisible. At 10,000 papers (a corpus sweep) it's $1,400 vs $100. At 100k papers it's the line between "tractable" and "no". **The infrastructure is there because the agent is paying retail price for every problem the infrastructure solves wholesale.**

### The 4-quadrant filter for new features

For every proposed item below, ask which quadrant it lands in:

1. **Constrain** the agent (closed vocabularies, qualifier sets) → agent does the hard contextual reading on a known surface. **Build.**
2. **Resolve** identifiers (bundled cross-refs, parsers for tool outputs) → agent doesn't waste tokens on solved problems. **Build.**
3. **Validate** the agent's output (cross-property SHACL, invariant checks) → catches failures the agent can't see in its own work. **Build.**
4. **Anything an agent could do as well freehand** (trivial shapes, hand-curated synonym scraps, regex CURIE checks). **Skip.**

The roadmap below leans heavily on quadrants 1–3. New PRs should justify themselves in those terms.

---

## v0.2.0 — RELEASED 2026-05-24

See CHANGELOG.md.

## v0.5.0 — RELEASED 2026-05-24 (audit-2 follow-up)

See CHANGELOG.md. Closes 5 of 7 actionable audit-2 findings (6a software
registry, 6b `uses_database`, 6c ignore-list, 6d accession→CURIE helper,
6e `acquired_from_matrix` qualifier, 6h `consolidates_dataset` qualifier).
Two items deferred to v0.6.0 (see candidates below).

## v0.4.0 — RELEASED 2026-05-24 (deferred audit items)

See CHANGELOG.md. Closes the three items the v0.3.1 release deferred:
SHACL tightening (finding #4), 5 study-level qualifiers for ASB heuristic
fields (finding #6), and the compound-name synonym layer (finding #7).

## v0.3.1 — RELEASED 2026-05-24 (audit follow-up)

See CHANGELOG.md. Closes finding #1 (Python floor), #2 (MSV/MW prefixes),
and #3 (CURIE enrichment) from the 2026-05-24 ASB-driven live audit.

## v0.3.0 — RELEASED 2026-05-24

See CHANGELOG.md.

Done items from the v0.3.0 candidate list:
- **RefMet canonical-name layer**: `refmet_name` populated for ~3.2k rows via
  per-InChIKey REST API (throttled, cached, gitignored cache). Fills
  `chemical_class`, `super_class`, `pathway` too. v0.3.0 was tagged at 628
  rows after the initial partial run; the cache has since been extended in
  the TSV shipped with v0.3.1. Cap is 5,000 priority rows (InChIKey + HMDB +
  KEGG/PubChem); re-run `build_data.py` to extend coverage incrementally.
- **Wikidata top-organisms sitelink ranking**: 53-species curated lookup (via
  P225 taxon name, two batches) + broad P31=Q16521 LIMIT 400 supplement.
  460 organisms with canonical QIDs.

## v0.6.0 candidates — deferred fuzzy/ML items from audit-2

These two audit-2 follow-ups did not ship in v0.5.0 because each needs a
dependency or design call that doesn't belong in a deterministic adapter
sprint. Both are tracked for v0.6.0:

- **Matrix-name fuzzy normalisation** (audit-2 finding 6e tier-2). The
  `acquired_from_matrix` qualifier ships in v0.5.0; the matrix-vocabulary
  itself does not. Sample matrices have heavy synonym tails ("feces" / "stool"
  / "fecal" / "poo"; "blood" / "plasma" / "serum" / "whole blood"; "leaf" /
  "leaves" / "foliage") where a sentence-transformer (e.g. `all-MiniLM-L6-v2`,
  22 MB) over a curated canonical list outperforms an ever-growing JSON.
  Decision needed: ship behind a `[ml]` extra so the wheel stays light, or
  emit a separate `indicium-adapters-metabolomics-matrices` package.
- **Tier-2 compound-synonym expansion via PubChem PUG-REST**. Audit-2 measured
  the synonym layer at 65% (gut metabolomics) / 71% (phenolics) / 76%
  (natural-product drugs). The hand-curated `_synonyms.json` (now 53 entries
  after v0.5.0) won't scale further. Plan: extend `build_data.py` with a
  PubChem fetcher that calls `/compound/name/<name>/synonyms/JSON` and
  `/compound/name/<name>/cids/JSON` for the highest-priority misses, caches
  to `_synonyms_cache.json` (gitignored), and writes a tier-2 JSON shipped
  with the wheel. Same offline-at-runtime constraint as the existing RefMet
  layer.

## v0.5.0 candidates (carried forward from v0.4.0)

The v0.4.0 release landed the three SHACL/qualifier/synonym items. Remaining
v0.4.0 candidates that did not ship:

- **mzTab-M SME (evidence) projection** — extend `parse_mztab_to_claims` to
  also emit `spectral_match` claims from SME rows.
- **Compress the bundled TSV** — gzip dropping ~22 MB to ~5 MB; CompoundIndex
  loads transparently.
- **Expand RefMet enrichment** — cover the remaining ~16k rows that have
  InChIKey + HMDB but not KEGG/PubChem.
- **Per-adapter qualifier-vocabulary SHACL** — currently the adapters'
  qualifier sets are advisory (used by `extraction_context()`) but no SHACL
  shape constrains the literal `asb:qualifier` value to that vocabulary.
  Adding one as `sh:Warning` (so composition doesn't cross-fire) would catch
  truly made-up qualifiers without false-positives across adapters.
- **Synonym layer expansion** — current `_synonyms.json` is ~30 entries
  hand-curated against the Wikidata-derived TSV. A maintainer pass through
  the most-common-name lists from MetaboAtlas, HMDB, and the Metabolomics
  Workbench RefMet API would expand this with low risk.

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
