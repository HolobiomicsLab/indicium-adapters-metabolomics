"""mzTab-M parser submodule — project SML+SMF sections into asb:Claim dicts.

PSI mzTab-M 2.0 standard: https://hupo-psi.github.io/mzTab/2_0-metabolomics-release/

Two claim types produced:
- 'identifies'  — one per SML (small-molecule summary) row, with chemical_name
                  as subject and database_identifier (CHEBI/HMDB/...) as object.
- 'has_feature' — one per SMF row.

Future (v0.3.0): SME (small-molecule evidence) rows → 'spectral_match' claims.
"""
from __future__ import annotations

from indicium_adapters_metabolomics.mztab.parser import parse_mztab_to_claims

__all__ = ["parse_mztab_to_claims"]
