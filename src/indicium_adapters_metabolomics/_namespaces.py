"""Hardcoded namespace URI constants for the three metabolomics adapters.

Per spec §2.2, this package has no runtime dependency on the metabokg or
earth_metabolome_ontology Python packages. All URIs are pinned here.
If an upstream namespace ever changes URI, update it in one place: this file.
"""
from __future__ import annotations

METABOLOMICS_PREFIXES: dict[str, str] = {
    "CHEBI":     "http://purl.obolibrary.org/obo/CHEBI_",
    "HMDB":      "https://hmdb.ca/metabolites/",
    # Public metabolomics-study repositories — accessions appear in paper text
    # as plain prefixed IDs (MTBLS####, ST######, MSV########) and the
    # MetaboKGAdapter's `annotated_in` qualifier and ASB's
    # metabolomics_metadata.data_accessions both reference them.
    "MTBLS":     "https://www.ebi.ac.uk/metabolights/",
    "MW":        "https://www.metabolomicsworkbench.org/data/DRCCStudySummary.php?Mode=SetupRawDataDownload&StudyID=",
    "MSV":       "https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?accession=",
    "KEGG":      "https://www.kegg.jp/entry/",
    "LIPIDMAPS": "https://www.lipidmaps.org/databases/lmsd/",
    "PUBCHEM":   "https://pubchem.ncbi.nlm.nih.gov/compound/",
    "WD":        "http://www.wikidata.org/entity/",
    "REFMET":    "https://www.metabolomicsworkbench.org/databases/refmet/refmet_details.php?REFMET_name=",
    "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
    "ENVO":      "http://purl.obolibrary.org/obo/ENVO_",
}

METABOKG_PREFIXES: dict[str, str] = {
    "MBS":  "https://ns.inria.fr/metaboKG/schema/",
    "MBD":  "https://ns.inria.fr/metaboKG/data/",
    "NPC":  "https://w3id.org/emi/npc#",
    "MS":   "http://purl.obolibrary.org/obo/MS_",
    "SIO":  "http://semanticscience.org/resource/SIO_",
    "PROV": "http://www.w3.org/ns/prov#",
    "USI":  "https://metabolomics-usi.ucsd.edu/dashinterface/?usi1=",
    "NCIT": "http://purl.obolibrary.org/obo/NCIT_",
}

EMI_PREFIXES: dict[str, str] = {
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
