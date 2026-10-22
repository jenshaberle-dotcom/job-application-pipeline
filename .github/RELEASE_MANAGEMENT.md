# JAP Classic release management

## Current publication path

Host audit on 2026-10-20: the installed updater still consumes immutable GitHub
release assets. The last published desktop generation is 1.2.6. GitHub is the
distribution channel; it is not the required execution platform.

The retained `.github/workflows/jap-windows-desktop-host-release.yml` depends on
retired Actions facades and is not a working RCC Direct release path.
`scripts/Build-JapClassicRelease.ps1` extracts its validation, build and double
payload verification into a PowerShell 7.1+ entry point without Actions context.
It requires a clean exact-source checkout and a fresh output directory, performs
Linux regression tests under WSL and package tests on Windows, and produces the
same four assets. It neither publishes nor installs them.

This entry point is currently an operator-local build, not an admitted native
RCC recipe. The native Windows service currently executes fixed project-source
checks. Release toolchain/workspace/network qualification and an explicit fixed
build profile are required before automatic RCC release execution can be enabled.
Do not interpret pool availability or a source-check PASS as release capability.

## Version and asset identity

The desktop product version is `windows/JAP.ControlCenter.Desktop/VERSION`.
The publication namespace is `jap-winapp-product-v<version>`.
Root `VERSION` and frontend package versions are separate component identifiers.

A product release binds exact source and publishes:

- `JAP-Control-Center-Desktop-win-x64.zip`
- `JAP-Control-Center-Desktop-win-x64.zip.sha256`
- `JAP-Control-Center-Runtime.zip`
- `JAP-Control-Center-Runtime.zip.sha256`

Embedded desktop/runtime identities and the frontend source marker must agree. Already
published tags/assets must not be overwritten. Private `.env`, CV/mail documents and DB
state are not release content. Installed updates use staged verification, consent and
transactional rollback; they never compile or fetch product source after consent.

## Engineering and publication gate

1. Review and merge the product change after required exact-head checks pass.
2. RCC admits an explicitly authorized publication workload for its exact source.
3. Run the standalone builder's Linux/Windows/frontend/product validation and asset integrity checks.
4. Publish only the qualified immutable identity; retain runtime/install proof separately.
5. Describe shipped behavior and remaining limitations in product-facing release notes.

Old `.github/release-requests/` and `.github/release-promotions/` records are historical
request formats. The active desktop workflow does not consume them. Adding such a record
or changing a version file does not publish or promote a release.

`.github/release.yml` groups generated notes by labels. Curated milestone notes may remain
in `.github/release-notes/`; past notes describe their original release, not current runtime.
See [Windows update contract](../docs/guides/jap_control_center_windows_app.md) and
[RCC execution](../docs/current/ci-max-execution.md).
