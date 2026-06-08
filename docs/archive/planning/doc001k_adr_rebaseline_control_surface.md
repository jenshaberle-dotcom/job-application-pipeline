# DOC-001K ADR Rebaseline Control Surface

Status: completed documentation-governance block

## Purpose

DOC-001 restored the Current Truth documentation path, but the ADR directory
still looked more authoritative than it safely was. Several ADRs were accepted
or proposed before the current Search Intelligence, governance, Control Center
and documentation-archive model existed.

DOC-001K creates a current ADR status surface before editing individual ADR
files.

## Implemented

DOC-001K adds:

- `docs/decisions/adr_status_table.md`
- `scripts/check_adr_rebaseline.py`
- `tests/test_doc001k_adr_rebaseline.py`

It also updates:

- `docs/decisions/adr/README.md`
- `docs/reference/governance/README.md`
- `docs/decisions/adr_rebaseline_plan.md`
- `docs/README.md`

## Important classifications

- ADR-017 is classified as `Superseded` for the active UI path because ADR-032
  established Jinja2 as the current intermediate Control Center template layer.
- ADR-019 is classified as `Needs rewrite` before dedicated heartbeat/source
  health work.
- ADR-020 is classified as `Needs rewrite` before role-family classification
  becomes an active pipeline feature.
- ADR-007 is classified as `Historical` because SSH setup is local workflow
  history, not current product architecture.

Most other ADRs remain `Current`, but they should be interpreted through the
Current Truth pointers in `docs/decisions/adr_status_table.md`.

## Validation

Run:

```bash
python scripts/check_adr_rebaseline.py --json
python scripts/check_documentation_references.py --write-report --json
python -m pytest -q tests/test_doc001k_adr_rebaseline.py tests/test_doc001j_documentation_reference_check.py
python -m pytest -q
```

Expected ADR result:

```text
status=pass
adr_file_count=33
table_row_count=33
issue_count=0
```

## Follow-up

DOC-001K is a control-surface block. It intentionally does not rewrite ADR-019
or ADR-020 inside the same PR.

Next safe options:

1. rewrite ADR-019 if heartbeat/source-health work is next,
2. rewrite ADR-020 if role-family classification is next,
3. continue the larger planning/source-analysis archive pass now that ADR and
   reference guards are in place,
4. return to STOP-002 / EO Search Intelligence work if documentation maturity is
   sufficient for the next implementation block.
