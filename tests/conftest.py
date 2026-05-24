"""Shared pytest fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture
def base_claim() -> dict:
    """A minimal 5-slot claim dict for adapter input."""
    return {
        "subject": "glucose",
        "qualifier": "identifies",
        "object": "blood plasma",
        "ontology_terms": {},
        "evidence_id": "fixture-001",
    }


@pytest.fixture
def empty_claim() -> dict:
    return {
        "subject": "",
        "qualifier": "identifies",
        "object": "",
        "ontology_terms": {},
        "evidence_id": "fixture-empty",
    }


@pytest.fixture
def metabokg_claim() -> dict:
    """A MetaboKG-style spectral_match claim."""
    return {
        "subject": "feature_42",
        "qualifier": "spectral_match",
        "object": "mzspec:MSV000087728:GNPS00002:scan:1234",
        "ontology_terms": {},
        "evidence_id": "fixture-mk-001",
    }


@pytest.fixture
def emi_interaction_claim() -> dict:
    """A METRIN-KG-style biotic interaction claim."""
    return {
        "subject": "Q132298",   # honey bee
        "qualifier": "pollinates",
        "object": "Q156495",     # apple tree
        "ontology_terms": {},
        "evidence_id": "fixture-emi-001",
    }
