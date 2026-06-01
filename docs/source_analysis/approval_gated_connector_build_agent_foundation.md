# S6C Approval-Gated Connector Build Agent Foundation

## Status

Implemented foundation.

## Purpose

S6B can now show when a bounded aggregator/search scope is saturated but still contains unresolved known candidates such as HDI. S6C turns that signal into a controlled connector-build path:

```text
unresolved origin candidate
+ repeated market evidence
+ passed early safety/relevance gates
→ approval-gated connector artifact build
→ connector validation
→ final approval gate
→ registration plan only after approval
```

The intent is to avoid an endless loop where the system repeatedly says "candidate unresolved" without allowing the agent workflow to prepare the artifacts needed to resolve it.

## Boundary

S6C may create a DB-backed build request and, after explicit build approval, write connector candidate artifacts.

S6C does not approve:

- auto-PR creation
- connector registration
- source activation
- Bronze persistence
- recurring ingestion
- scheduler changes
- CSV/Excel/export artifacts as pipeline inputs

## Build Modes

### `connector_candidate_from_gate_evidence`

Used when the normal connector-candidate gates are already sufficient. The build can proceed after explicit build approval and still remains only an artifact dry run.

### `bounded_investigation_connector`

Used as a controlled escape hatch for unresolved candidates with high false-negative pressure. This mode is allowed only when early safety and relevance gates passed but concrete detail evidence could not yet be established.

This is intentionally not a registration approval. It allows the repository to contain a bounded connector candidate so validation and review can continue with real code instead of staying blocked at abstract evidence.

## Approval Model

S6C separates three decisions:

1. **Build approval** — may write connector artifact files.
2. **Final approval** — may approve connector registration.
3. **Controlled activation** — may activate a source/search profile later.

Only the first decision belongs to S6C. Registration and activation remain separate gates.

## Example Commands

Preview the build decision:

```bash
python -m scripts.run_approval_gated_connector_build_agent \
  --company-key hdi \
  --reviewed-by jens \
  --write
```

If the preview recommends explicit build approval, run:

```bash
python -m scripts.run_approval_gated_connector_build_agent \
  --company-key hdi \
  --reviewed-by jens \
  --approve-build \
  --write
```

Then validate the generated connector candidate:

```bash
python -m scripts.run_employer_origin_connector_validation_agent \
  --company-key hdi \

```

## Expected HDI Path

HDI may remain blocked for direct generation if the detail-evidence gate still cannot find concrete detail pages. S6C handles that state explicitly:

```text
high false-negative pressure
+ passed early gates
+ no connector artifacts yet
→ request explicit build approval
→ bounded investigation connector artifacts may be written
→ validation decides whether the artifacts are useful enough
```

This closes the gap between Search Intelligence learning and actionable connector work while preserving hard approval gates.
