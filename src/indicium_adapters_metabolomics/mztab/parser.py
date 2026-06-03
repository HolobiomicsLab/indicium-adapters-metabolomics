"""mzTab-M to asb:Claim projection (SML + SMF sections).

Implementation note: we deliberately avoid pyteomics's full mzTab loader
because v4.7 doesn't fully support mzTab-M 2.0 (it targets older mzTab 1.0).
Instead we parse the tab-separated sections directly, which is simpler and
gives us full control over the SML/SMF semantics.
"""
from __future__ import annotations

from pathlib import Path


def parse_mztab_to_claims(mztab_path: Path | str) -> list[dict]:
    """Parse an .mztab file's SML and SMF sections, return a list of asb:Claim dicts.

    Each claim has the 5-slot shape: subject, qualifier, object, ontology_terms, evidence_id.
    Raises FileNotFoundError if the file doesn't exist.
    """
    path = Path(mztab_path)
    if not path.exists():
        raise FileNotFoundError(f"mzTab file not found: {path}")

    sml_header: list[str] | None = None
    smf_header: list[str] | None = None
    sml_rows: list[dict[str, str]] = []
    smf_rows: list[dict[str, str]] = []

    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line or line.startswith(("COM", "MTD")):
                continue
            fields = line.split("\t")
            tag = fields[0]
            if tag == "SMH":
                sml_header = fields
            elif tag == "SML" and sml_header:
                # strict=False: trailing columns may be absent in sparse rows
                sml_rows.append(dict(zip(sml_header, fields, strict=False)))
            elif tag == "SFH":
                smf_header = fields
            elif tag == "SMF" and smf_header:
                # strict=False: trailing columns may be absent in sparse rows
                smf_rows.append(dict(zip(smf_header, fields, strict=False)))

    claims: list[dict] = []
    file_id = path.stem

    # SML → identifies claims
    for row in sml_rows:
        sml_id = row.get("SML_ID", "")
        name = row.get("chemical_name", "").strip()
        db_id = row.get("database_identifier", "").strip()
        if not (name or db_id):
            continue
        claim: dict = {
            "subject": name or db_id,
            "qualifier": "identifies",
            "object": db_id,
            "ontology_terms": {},
            "evidence_id": f"mztab:{file_id}:SML:{sml_id}",
        }
        if ":" in db_id:
            claim["ontology_terms"]["object"] = db_id
            # database_identifier is a curated CURIE taken verbatim from the
            # mzTab file (produced by an upstream identification tool).
            claim.setdefault("ontology_term_justifications", {})["object"] = (
                "semapv:CompositeMatching"
            )
        claims.append(claim)

    # SMF → has_feature claims
    for row in smf_rows:
        smf_id = row.get("SMF_ID", "")
        claims.append({
            "subject": f"sml:{file_id}",
            "qualifier": "has_feature",
            "object": f"smf:{file_id}:{smf_id}",
            "ontology_terms": {},
            "evidence_id": f"mztab:{file_id}:SMF:{smf_id}",
        })

    return claims
