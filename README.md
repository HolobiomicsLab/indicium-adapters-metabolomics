# indicium-adapters-metabolomics

Metabolomics-domain DomainAdapters for the [indicium](https://github.com/holobiomicslab/indicium) ecosystem.

Bundles three adapters in one wheel:

- **`MetabolomicsAdapter`** — generic MS/NMR metabolomics claims; CHEBI/HMDB/KEGG/LIPIDMAPS/PubChem/Wikidata enrichment via a bundled RefMet+BridgeDb compound index.
- **`MetaboKGAdapter`** — MetaboKG-flavored claims (GNPS spectral matches, NPC chemical classification, MSI annotation levels, FBMN features).
- **`EMIAdapter`** — Earth Metabolome Initiative (ENPKG) analytical claims AND METRIN-KG ecological/trait claims (biotic interactions, plant traits, body-part qualified observations).

All three register under the `indicium.adapters` entry-point group and are discoverable via `indicium_adapters.discover_adapters()`.

## Install

```bash
pip install indicium-adapters-metabolomics
```

## Usage

```python
from indicium_adapters import discover_adapters, compose_adapters

# Use one adapter
adapter = discover_adapters()["metabolomics"]
enriched = adapter.enrich_claim({
    "subject": "glucose", "qualifier": "identifies", "object": "",
    "ontology_terms": {}, "evidence_id": "abc",
})
# enriched["ontology_terms"]["subject"] == "CHEBI:17234"
# enriched["xrefs"]["subject"]["hmdb"] == "HMDB0000122"

# Use all three composed
composite = compose_adapters(list(discover_adapters().values()))
# composite.domain_id is "+"-joined in discover_adapters() iteration order
# (typically alphabetical: "emi+metabokg+metabolomics").
# To control order, pass an explicit list, e.g.:
#   compose_adapters([adapters["metabolomics"], adapters["metabokg"], adapters["emi"]])
```

## SHACL shapes

Each adapter ships `shacl_shapes()` returning an `rdflib.Graph` of NodeShapes
targeting `asb:Claim` graphs. Pipeline RDF validation (MBS:, emi: classes)
stays in the upstream `metabokg` / `earth_metabolome_ontology` repos.

## Development

```bash
git clone https://github.com/holobiomicslab/indicium-adapters-metabolomics
cd indicium-adapters-metabolomics
pip install -e .[dev]
pytest
```

See `CLAUDE.md` for the dev guide.

## License

See `LICENSE`. Bundled RefMet data: CC-BY (Metabolomics Workbench). Bundled BridgeDb data: CC0.
