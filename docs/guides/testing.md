# Validation

Use Python 3.12 and a project virtual environment. Dependency definitions are
`requirements.txt`, `requirements-dev.txt` and the RCC package set. These have different
purposes; RCC owns runner/toolchain qualification.

```bash
python -m pip install -r requirements-dev.txt
python scripts/run_validate001_unified_validation.py --profile quick
python scripts/run_validate001_unified_validation.py --profile commit
```

`quick` checks engineering tooling, rules and diffs. `commit` additionally runs the full
pytest suite. Focused tests are useful during editing but do not replace required exact-head CI.

## Documentation changes

```bash
python scripts/check_documentation_references.py --json
python scripts/check_documentation_architecture.py --json
python scripts/check_adr_rebaseline.py --json
python scripts/check_classic_documentation_truth.py
```

The reference checker checks file/path references; it does not establish semantic correctness,
remote URL availability or Mermaid rendering. The truth guard checks current documentation
against configured UI, workflow demands and retired active-document paths.

## Product and frontend

```bash
python -m pytest -q
npm ci --prefix frontend/control-center
npm run build --prefix frontend/control-center
```

Use local fixtures for parser/connector unit tests. Separate tests from live acquisition,
private database inspection, provider calls and productive apply. A full local test pass is
repository evidence, not proof of live source coverage, Top 5, installed update recovery or
RCC fleet operation.

## URL-Finder integration regression checks

Run `python -m pytest -q tests/test_hannover_tech_registry_poc.py tests/test_hannover_profile_market.py tests/test_hannover_solution_architecture_staging.py tests/portal_discovery`.
These are offline tests. Stored field replay additionally checks exact outcomes
without fresh HTTP calls. Neither test mode establishes live 90% coverage or
production daily delivery. See [review](../current/URLFINDER-SOURCE-INTEGRATION.md).
