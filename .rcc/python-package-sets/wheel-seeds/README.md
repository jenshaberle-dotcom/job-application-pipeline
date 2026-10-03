# Reviewed passive dependency artifact

`jstyleson-0.0.2-py3-none-any.whl` is built from unchanged PyPI source because
upstream publishes no wheel. Its source and wheel SHA-256 values and build inputs
are recorded in `jstyleson-0.0.2.provenance.json`; the wheel hash is also pinned in
the JAP package-set lock. This is a dependency artifact, not a runner profile,
installer, selection rule or lifecycle authority.

Before the first workload with this package lock, the RCC operator fetches the
wheel from the exact JAP candidate SHA into a passive RCC wheel-seed cache and
verifies its hash. Set `PIP_FIND_LINKS` to that local directory for the existing
RCC controller process. The existing materializer uses binary-only/no-deps/hash-
qualified download, verifies the complete wheel inventory, caches it by lock hash,
and installs the qualified runtime offline. No source build occurs during CI.
Subsequent runs reuse the existing content-addressed wheel cache.

Only the wheel belongs in the seed directory. Do not copy this README or provenance
into RCC's complete wheelhouse. Never replace an existing immutable artifact with
unverified bytes. Normal package dependencies remain on the public package index.
