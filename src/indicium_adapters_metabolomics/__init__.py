"""indicium-adapters-metabolomics — metabolomics-domain adapters for the indicium ecosystem.

Bundles MetabolomicsAdapter (base), MetaboKGAdapter (MetaboKG-flavored claims),
and EMIAdapter (Earth Metabolome Initiative + METRIN-KG ecological claims).
All three are exposed via the `indicium.adapters` entry-point group.
"""
from __future__ import annotations

from indicium_adapters_metabolomics.emi import EMIAdapter
from indicium_adapters_metabolomics.metabokg import MetaboKGAdapter
from indicium_adapters_metabolomics.metabolomics import MetabolomicsAdapter
from indicium_adapters_metabolomics.mztab import parse_mztab_to_claims

__version__ = "0.2.0"
__all__ = ["EMIAdapter", "MetaboKGAdapter", "MetabolomicsAdapter", "parse_mztab_to_claims"]
