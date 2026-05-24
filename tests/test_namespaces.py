"""Tests for the hardcoded namespace constants."""
from __future__ import annotations

from indicium_adapters_metabolomics import _namespaces as ns


def test_metabolomics_prefixes_complete():
    assert ns.METABOLOMICS_PREFIXES == {
        "CHEBI":     "http://purl.obolibrary.org/obo/CHEBI_",
        "HMDB":      "https://hmdb.ca/metabolites/",
        "MTBLS":     "https://www.ebi.ac.uk/metabolights/",
        "KEGG":      "https://www.kegg.jp/entry/",
        "LIPIDMAPS": "https://www.lipidmaps.org/databases/lmsd/",
        "PUBCHEM":   "https://pubchem.ncbi.nlm.nih.gov/compound/",
        "WD":        "http://www.wikidata.org/entity/",
        "REFMET":    "https://www.metabolomicsworkbench.org/databases/refmet/refmet_details.php?REFMET_name=",
        "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
        "ENVO":      "http://purl.obolibrary.org/obo/ENVO_",
    }


def test_metabokg_prefixes_complete():
    assert ns.METABOKG_PREFIXES == {
        "MBS":  "https://ns.inria.fr/metaboKG/schema/",
        "MBD":  "https://ns.inria.fr/metaboKG/data/",
        "NPC":  "https://w3id.org/emi/npc#",
        "MS":   "http://purl.obolibrary.org/obo/MS_",
        "SIO":  "http://semanticscience.org/resource/SIO_",
        "PROV": "http://www.w3.org/ns/prov#",
        "USI":  "https://metabolomics-usi.ucsd.edu/dashinterface/?usi1=",
        "NCIT": "http://purl.obolibrary.org/obo/NCIT_",
    }


def test_emi_prefixes_complete():
    assert ns.EMI_PREFIXES == {
        "emi":      "https://w3id.org/emi#",
        "emiBox":   "https://w3id.org/emi/abox#",
        "emiUnit":  "https://w3id.org/emi/unit#",
        "NPC":      "https://w3id.org/emi/npc#",
        "sosa":     "http://www.w3.org/ns/sosa/",
        "WD":       "http://www.wikidata.org/entity/",
        "qudt":     "http://qudt.org/schema/qudt/",
        "qudtUnit": "http://qudt.org/vocab/unit/",
        "RO":       "http://purl.obolibrary.org/obo/RO_",
        "UBERON":   "http://purl.obolibrary.org/obo/UBERON_",
        "PATO":     "http://purl.obolibrary.org/obo/PATO_",
        "PO":       "http://purl.obolibrary.org/obo/PO_",
        "ENVO":     "http://purl.obolibrary.org/obo/ENVO_",
        "USI":      "https://metabolomics-usi.ucsd.edu/dashinterface/?usi1=",
        "InChIKey": "https://www.ebi.ac.uk/unichem/sources/inchikey/",
    }


def test_shared_npc_consistent():
    """NPC appears in both MetaboKG and EMI prefix dicts; both must map to the same URI."""
    assert ns.METABOKG_PREFIXES["NPC"] == ns.EMI_PREFIXES["NPC"]
