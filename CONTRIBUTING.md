# Contributing to indicium-adapters-metabolomics

Thanks for your interest!

## Setup

```bash
git clone https://github.com/HolobiomicsLab/indicium-adapters-metabolomics
cd indicium-adapters-metabolomics
pip install -e .[dev]
```

## Development workflow

1. Create a feature branch from `main`.
2. Write tests first (TDD). The suite is `pytest`.
3. Run `ruff check .` and `pytest` before pushing.
4. Open a PR describing the change.

## Adding a qualifier

See [CLAUDE.md § Adding a new qualifier](CLAUDE.md#adding-a-new-qualifier).

## Refreshing bundled data

See [CLAUDE.md § Refreshing bundled data files](CLAUDE.md#refreshing-bundled-data-files).
The `build_data.py` and `build_vocabs.py` scripts hit live external services
(Wikidata SPARQL, OBO Foundry, npc_taxonomy.ttl) and are maintainer-only.

## Code of conduct

By participating you agree to abide by the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
