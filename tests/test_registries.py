"""Tests for the v0.5.0 software registry + accession-prefix helpers.

These close audit-2 findings 6a (canonical software names), 6b (database vs
software disambiguation), 6c (general-purpose language ignore-list), and
6d (bare repository accession → CURIE normalisation).
"""
from __future__ import annotations

import pytest

from indicium_adapters_metabolomics import (
    accession_to_curie,
    canonical_software_name,
    is_ignored_tool_name,
    is_metabolomics_database,
    is_metabolomics_tool,
)

# --- canonical_software_name -----------------------------------------------

@pytest.mark.parametrize("alias,canonical", [
    ("MS-DIAL",   "MS-DIAL"),
    ("ms-dial",   "MS-DIAL"),
    ("msdial",    "MS-DIAL"),
    ("MSDIAL",    "MS-DIAL"),
    ("MS DIAL",   "MS-DIAL"),
    ("MZmine",    "MZmine"),
    ("mzmine",    "MZmine"),
    ("MZmine 3",  "MZmine"),
    ("mzmine3",   "MZmine"),
    ("GNPS",      "GNPS"),
    ("gnps2",     "GNPS"),
    ("SIRIUS",    "SIRIUS"),
    ("CSI:FingerID", "SIRIUS"),
    ("XCMS",      "XCMS"),
    ("MetaboAnalyst", "MetaboAnalyst"),
])
def test_canonical_software_name_canonicalises_known_aliases(alias, canonical):
    assert canonical_software_name(alias) == canonical


def test_canonical_software_name_handles_whitespace():
    assert canonical_software_name("  MS-DIAL  ") == "MS-DIAL"


@pytest.mark.parametrize("name", ["", "   ", "not-a-tool", "FooBar"])
def test_canonical_software_name_returns_none_on_unknown(name):
    assert canonical_software_name(name) is None


# --- is_metabolomics_tool --------------------------------------------------

@pytest.mark.parametrize("name", ["MS-DIAL", "MZmine", "GNPS", "SIRIUS", "XCMS",
                                  "Cytoscape", "QIIME"])
def test_is_metabolomics_tool_recognises_canonical_names(name):
    assert is_metabolomics_tool(name)


@pytest.mark.parametrize("name", ["msdial", "GNPS2", "mzmine 3"])
def test_is_metabolomics_tool_recognises_aliases(name):
    assert is_metabolomics_tool(name)


@pytest.mark.parametrize("name", ["", "Python", "ChEBI", "random-string"])
def test_is_metabolomics_tool_rejects_non_tools(name):
    # Databases and ignored names are not "tools".
    assert not is_metabolomics_tool(name)


# --- is_metabolomics_database ----------------------------------------------

@pytest.mark.parametrize("name", ["ChEBI", "HMDB", "KEGG", "PubChem",
                                  "MetaboLights", "MassIVE", "GNPS-LIBRARIES",
                                  "Wikidata", "MoNA"])
def test_is_metabolomics_database_recognises_dbs(name):
    assert is_metabolomics_database(name)


def test_is_metabolomics_database_case_insensitive():
    assert is_metabolomics_database("chebi")
    assert is_metabolomics_database("HMDB")


@pytest.mark.parametrize("name", ["", "MS-DIAL", "Python", "made-up-db"])
def test_is_metabolomics_database_rejects_non_dbs(name):
    assert not is_metabolomics_database(name)


# --- is_ignored_tool_name --------------------------------------------------

@pytest.mark.parametrize("name", ["Python", "R", "Jupyter", "GitHub",
                                  "pandas", "Docker", "Conda"])
def test_is_ignored_tool_name_recognises_general_purpose_names(name):
    assert is_ignored_tool_name(name)


@pytest.mark.parametrize("name", ["", "MS-DIAL", "ChEBI", "GNPS"])
def test_is_ignored_tool_name_rejects_metabolomics_specific_names(name):
    assert not is_ignored_tool_name(name)


def test_disjoint_buckets_for_common_inputs():
    """A single name should never be classified into more than one of
    (canonical software, database, ignored)."""
    samples = ["MS-DIAL", "MZmine", "GNPS", "SIRIUS",
               "ChEBI", "HMDB", "MetaboLights",
               "Python", "R", "GitHub"]
    for s in samples:
        buckets = (is_metabolomics_tool(s), is_metabolomics_database(s),
                   is_ignored_tool_name(s))
        # Exactly one True.
        assert sum(buckets) == 1, f"{s!r} -> {buckets}"


# --- accession_to_curie ----------------------------------------------------

@pytest.mark.parametrize("raw,curie", [
    ("ST002320",      "MW:ST002320"),
    ("st002320",      "MW:ST002320"),       # case-folds
    ("ST123456789",   "MW:ST123456789"),    # long IDs OK
    ("MSV000088235",  "MSV:MSV000088235"),
    ("msv000088235",  "MSV:MSV000088235"),
    ("MTBLS1234",     "MTBLS:MTBLS1234"),
    ("MTBLS9",        "MTBLS:MTBLS9"),
])
def test_accession_to_curie_normalises_bare_accessions(raw, curie):
    assert accession_to_curie(raw) == curie


def test_accession_to_curie_passes_through_curies_unchanged():
    """Already-prefixed CURIEs should round-trip."""
    for c in ("MW:ST002320", "MSV:MSV000088235", "MTBLS:MTBLS1234",
              "CHEBI:17234"):
        assert accession_to_curie(c) == c


@pytest.mark.parametrize("raw", ["", "   ", "ST", "ST123", "FOO12345",
                                 "GSE12345", "PXD000001"])
def test_accession_to_curie_returns_none_on_unrecognised(raw):
    # PXD/GSE are real prefixes but not in our metabolomics scope yet —
    # caller decides what to do.
    assert accession_to_curie(raw) is None
