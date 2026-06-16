# Pipeline linting baseline

PIPELINE-LINT-001B introduces Ruff as an explicit development lint tool for the
job-application-pipeline project.

## Current gate status

Ruff is a development/tooling baseline, not yet a hard MCP target gate.

The current MCP target validation gate remains:

    pytest -q

Ruff may be promoted to the MCP target validation gate only after a reviewed
baseline run is green for the agreed project scope.

## Scope

The initial Ruff configuration is intentionally conservative:

- `E4`, `E7`, `E9`
- `F`

This focuses on correctness-oriented checks such as syntax/import problems and
Pyflakes findings. It intentionally avoids a broad style cleanup campaign.

## Exclusions

The configuration excludes local/runtime artifacts and retired chat-continuation
legacy archives. These exclusions must not be used to hide active code problems.
They only keep review-output and archived legacy material out of the first lint
baseline.

## Intended workflow

    python -m pip install -r requirements-dev.txt
    ruff check . --statistics
    ruff check .

If Ruff reports many findings, split remediation into a dedicated follow-up block
before making Ruff a hard MCP target gate.
