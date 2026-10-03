# Reviewed passive dependency artifact

`jstyleson-0.0.2-py3-none-any.whl` is built from unchanged PyPI source because
upstream publishes no wheel. Its source and wheel SHA-256 values and build inputs
are recorded in `jstyleson-0.0.2.provenance.json`; the wheel hash is also pinned in
the JAP package-set lock. This is a dependency artifact, not a runner profile,
installer, selection rule or lifecycle authority.

The dependency declaration includes this artifact under
`project_runtime.python.package_set.wheel_seeds`. RCC's existing artifact
preparation fetches it and its provenance from the admitted exact JAP source,
checks package/hash/platform identity and supplies the qualified local artifact
to binary-only/no-deps/hash-required download. It authenticates the complete
inventory before atomic cache publication and offline runtime installation.
`--prepare-only`, environment preparation and normal materialization share this
path. A warm cache is reused without a seed download. No manual seed fetch or
shell-exported `PIP_FIND_LINKS` is required after the RCC extension is adopted.
No source build occurs during CI.

Only the wheel belongs in the seed directory. Do not copy this README or provenance
into RCC's complete wheelhouse. Never replace an existing immutable artifact with
unverified bytes. Normal package dependencies remain on the public package index.
