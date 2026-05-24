"""Tests that the three adapters are registered and discoverable."""
from __future__ import annotations

from importlib.metadata import entry_points

from indicium_adapters import discover_adapters


def test_entry_points_registered():
    eps = {ep.name for ep in entry_points(group="indicium.adapters")
           if ep.module.startswith("indicium_adapters_metabolomics")}
    assert eps == {"metabolomics", "metabokg", "emi"}


def test_discover_adapters_finds_all_three():
    found = discover_adapters()
    for name in ("metabolomics", "metabokg", "emi"):
        assert name in found, f"discover_adapters() missing {name!r}; found={sorted(found)}"


def test_discovered_adapters_have_expected_api_version():
    for name in ("metabolomics", "metabokg", "emi"):
        assert discover_adapters()[name].api_version == 1
