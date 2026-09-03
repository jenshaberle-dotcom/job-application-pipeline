# Release Management

GitHub Releases are the product-facing history of the Job Application Pipeline. Commit history remains engineering detail; a release must explain what changed for operators and users, including relevant bug fixes and known limitations.

## Versioning

Use SemVer-compatible tags with a leading `v`:

- `v0.x.y-*` — pre-production development and demo/RC releases.
- `v0.x.y-demo.N` — explicitly demo-oriented checkpoints.
- `v0.x.y-rc.N` — release candidates intended for broader product validation.
- `v1.0.0` and later — only after an explicit production-readiness decision.

Version changes describe product compatibility and visible behavior, not the number of commits.

## Release authority

The only canonical release path is `.github/workflows/release.yml`, dispatched from `main`.

The workflow:

1. requires `main` as release authority;
2. validates the requested version;
3. refuses to overwrite an existing tag;
4. binds the tag to the exact checked-out `main` SHA;
5. uses a curated notes file when supplied, otherwise GitHub generated release notes;
6. publishes the GitHub tag and Release together.

Do not create ad-hoc product tags from feature branches.

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

Use curated notes for milestone/demo releases or when generated notes would include too much historical noise. Store them under `.github/release-notes/` and pass the path to the release workflow.

A curated release should contain:

- highlights;
- bug fixes;
- product/data changes;
- operator or deployment changes;
- known limitations;
- safety/authority boundaries when relevant.

Runtime facts that are not shipped in Git must be labeled as operator validation, not represented as repository state.

## Release quality gate

Before publishing a release:

- the target change must already be merged to `main`;
- normal repository CI and re-entry identity must be green for the merged work;
- local-only runtime claims must have a current operator proof when the release notes depend on them;
- known material limitations must be stated rather than hidden.

Release notes are part of the product contract and should be reviewed with the same care as operator-facing UI text.
