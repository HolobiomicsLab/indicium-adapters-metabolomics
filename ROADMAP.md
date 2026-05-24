# Roadmap

Items explicitly out of scope for v0.1.0, kept here for future minor releases.

## v0.2.0 candidates

- **Expand bundled TSV.** Run `build_data.py` against live RefMet + BridgeDb. Target ≥10,000 compounds.
- **Grow inline vocabularies:** NPC pathways (currently 10 → full ~150), plant parts (10 → ~50), interaction types (10 → ~30), Wikidata top-organisms (0 → 200).
- **mzTab-M parser** as `indicium_adapters_metabolomics.mztab` submodule: project SML/SMF/SME rows from `.mztab` files into `asb:Claim` dicts.

## v0.3.0+ candidates

- **`[enrichment]` optional extra** for live ChEBI/PubChem REST lookup with on-disk caching.
- **`query_claims(question)` Protocol extension** for KG-backed SPARQL adapters (requires bumping `indicium-adapters.CURRENT_API_VERSION` to 2; coordinated release across consumers).
- **Live MetaboKG SPARQL endpoint adapter** once an endpoint URL stabilizes.
- **Sibling packages:** `indicium-adapters-lipidomics` (ChEMBL + LIPIDMAPS lipid-class hierarchy), `indicium-adapters-proteomics`.
