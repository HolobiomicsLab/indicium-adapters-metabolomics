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

## Future / v0.5.0+ candidates

- **`[enrichment]` optional extra** for live ChEBI/PubChem REST lookup with on-disk caching.
- **`query_claims(question)` Protocol extension** for KG-backed SPARQL adapters (requires bumping `indicium-adapters.CURRENT_API_VERSION` to 2; coordinated release across consumers).
- **Live MetaboKG SPARQL endpoint adapter** once an endpoint URL stabilizes.
- **Sibling packages:** `indicium-adapters-lipidomics` (ChEMBL + LIPIDMAPS lipid-class hierarchy), `indicium-adapters-proteomics`.
