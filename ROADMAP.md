# Roadmap

Items explicitly out of scope for v0.1.0, kept here for future minor releases.

## v0.2.0 — RELEASED 2026-05-24

See CHANGELOG.md.

## v0.3.0 candidates

- **RefMet canonical-name layer** — wire the bulk RefMet API and populate the
  `refmet_name` column of the compound TSV (currently empty).
- **mzTab-M SME (evidence) projection** — extend `parse_mztab_to_claims` to
  also emit `spectral_match` claims from SME rows.
- **Compress the bundled TSV** — gzip dropping ~22 MB to ~5 MB; CompoundIndex
  loads transparently.
- **Re-do top-organisms SPARQL with sitelink ranking** — the v0.2.0 list is a
  random Q16521 sample; query a paginated approach to actually get
  most-recognized taxa.

## Future / v0.4.0+ candidates

- **`[enrichment]` optional extra** for live ChEBI/PubChem REST lookup with on-disk caching.
- **`query_claims(question)` Protocol extension** for KG-backed SPARQL adapters (requires bumping `indicium-adapters.CURRENT_API_VERSION` to 2; coordinated release across consumers).
- **Live MetaboKG SPARQL endpoint adapter** once an endpoint URL stabilizes.
- **Sibling packages:** `indicium-adapters-lipidomics` (ChEMBL + LIPIDMAPS lipid-class hierarchy), `indicium-adapters-proteomics`.
