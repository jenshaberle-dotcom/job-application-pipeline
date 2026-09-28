# Release Management

GitHub Releases are the product-facing history of the Job Application Pipeline. Commit history remains engineering detail; a release must explain what changed for operators and users, including relevant bug fixes and known limitations.

## Versioning

Use SemVer-compatible tags with a leading `v`:

- `v0.x.y-*` — pre-production development and demo/RC releases.
- `v0.x.y-demo.N` — explicitly demo-oriented checkpoints.
- `v0.x.y-rc.N` — release candidates intended for broader product validation.
- `v1.0.0` and later — only after an explicit production-readiness decision.

Version changes describe product compatibility and visible behavior, not the number of commits.

A GitHub **pre-release flag** and the semantic version are separate concerns. A demo/RC tag may remain clearly non-production by version/name/notes while still being promoted to a normal published GitHub Release when repository visibility is desired.

## Release authority

Release publication is currently **blocked pending an RCC-assigned Windows
workload and exact-source qualification**. No active publisher exists in this
repository. A version-file change or release request does not publish a release.

Prepare notes and requests through a normal PR. Publication must use the RCC
admission, reservation, assignment, verification and cleanup contract in
`docs/current/ci-max-execution.md`. The publisher must bind immutable artifacts
and tags to the validated main SHA. Do not restore retired execution workflows
or create ad-hoc product tags from feature branches.

### Release request schema

Example:

```json
{
  "schema": "job_application_pipeline.release_request.v1",
  "version": "0.1.0-demo.1",
  "release_name": "DEMO-001 Salvaged Product Path",
  "prerelease": true,
  "notes_file": ".github/release-notes/v0.1.0-demo.1.md"
}
```

The request filename must equal the normalized version with a leading `v`, for example `.github/release-requests/v0.1.0-demo.1.json`.

Release-request files are durable audit records. Do not repurpose or edit an already-published version request.

## Release promotion

GitHub's repository summary can hide a release that is flagged as a pre-release and display `No releases published` even though a real Release object exists. When a checkpoint should be visible as a normal published release without changing its immutable tag, use a GitOps promotion request.

Example:

```json
{
  "schema": "job_application_pipeline.release_promotion.v1",
  "version": "0.1.0-demo.1",
  "reason": "Expose the audited demo checkpoint in the normal GitHub Releases surface."
}
```

Store it as `.github/release-promotions/v0.1.0-demo.1.json` through a normal PR.
Requests remain inert until RCC-assigned publication is qualified. A promotion
must verify the existing immutable tag and release, and change only visibility;
it must not recreate tags or rewrite notes.

Promotion does **not** imply production readiness. Product maturity remains defined by the version, release name, release notes, known limitations and explicit product decisions.

## Release-note categories

`.github/release.yml` groups merged PRs by labels. Use one primary release label whenever practical:

- `breaking-change` / `breaking`
- `bug` / `bugfix` / `fix`
- `enhancement` / `feature`
- `data` / `origin` / `connector`
- `application` / `ranking`
- `ui` / `ux`
- `infrastructure` / `ci` / `build`
- `documentation` / `docs`
- `dependencies`
- `skip-release` only for changes that must intentionally stay out of generated release notes.

A bug fix should be described in product terms: symptom, correction, and the proof or boundary that prevents recurrence. Do not use commit IDs as the only explanation.

## Curated notes

Use curated notes for milestone/demo releases or when generated notes would include too much historical noise. Store them under `.github/release-notes/` and reference the path from the release request or manual workflow input.

A curated release should contain:

- highlights;
- bug fixes;
- product/data changes;
- operator or deployment changes;
- known limitations;
- safety/authority boundaries when relevant.

Runtime facts that are not shipped in Git must be labeled as operator validation, not represented as repository state.

## Release quality gate

Before publishing or promoting a release:

- the governing request must already be merged to `main`;
- RCC-assigned repository validation and re-entry identity must pass for the exact request/promotion target;
- local-only runtime claims must have a current operator proof when the release notes depend on them;
- known material limitations must be stated rather than hidden;
- an existing version tag is immutable and must never be overwritten.

Release notes are part of the product contract and should be reviewed with the same care as operator-facing UI text.
