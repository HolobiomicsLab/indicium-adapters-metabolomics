"""indicium-adapters-metabolomics — metabolomics-domain adapters for the indicium ecosystem.

Bundles MetabolomicsAdapter (base), MetaboKGAdapter (MetaboKG-flavored claims),
and EMIAdapter (Earth Metabolome Initiative + METRIN-KG ecological claims).
All three are exposed via the `indicium.adapters` entry-point group.

The `_registries` helpers (`canonical_software_name`, `is_metabolomics_tool`,
`is_metabolomics_database`, `is_ignored_tool_name`, `accession_to_curie`) are
re-exported here for bridge layers that need to clean ASB free-text tool lists
or normalise repository accessions before emitting claims.
"""
from __future__ import annotations

from indicium_adapters_metabolomics._registries import (
    accession_to_curie,
    canonical_software_name,
    is_ignored_tool_name,
    is_metabolomics_database,
    is_metabolomics_tool,
)
from indicium_adapters_metabolomics.emi import EMIAdapter
from indicium_adapters_metabolomics.metabokg import MetaboKGAdapter
from indicium_adapters_metabolomics.metabolomics import MetabolomicsAdapter
from indicium_adapters_metabolomics.mztab import parse_mztab_to_claims

__version__ = "0.5.0"
__all__ = [
    "EMIAdapter",
    "MetaboKGAdapter",
    "MetabolomicsAdapter",
    "accession_to_curie",
    "canonical_software_name",
    "is_ignored_tool_name",
    "is_metabolomics_database",
    "is_metabolomics_tool",
    "parse_mztab_to_claims",
]
