# DEMO-001 operator test preparation

This note is a repository-side preparation aid only. It does not assert current local DB/Product readiness.

The canonical operator test order remains:

1. refresh local `main`;
2. inspect the local schema/migration frontier;
3. apply only a specifically qualified exact migration when the repository says it is safe;
4. run the canonical full demo preflight;
5. start the Control Center only after a real local READY result.

A small operator preparation command is provided by `scripts/prepare_product_v1_demo_operator_test.py`.

Default mode is read-only:

```bash
python scripts/prepare_product_v1_demo_operator_test.py
```

It reports repository identity and the existing Product V1 demo schema-readiness projection. It never mutates the database and never promotes readiness.

If and only if the output explicitly reports `QUALIFIED_EXACT_104`, the operator may run:

```bash
python scripts/prepare_product_v1_demo_operator_test.py --apply-qualified-104
```

The command re-checks the live DB immediately before apply and delegates to the existing exact migration runner with `--require-sole-pending`. It refuses multiple pending migrations, checksum mismatches, failed required tracking, missing repository migration files, or any target other than `104_create_product_v1_ranking_score_reviews.sql`.

After schema readiness is real, the same helper can launch the canonical preflight:

```bash
python scripts/prepare_product_v1_demo_operator_test.py --run-preflight
```

or, when exact 104 is the sole qualified pending migration:

```bash
python scripts/prepare_product_v1_demo_operator_test.py \
  --apply-qualified-104 \
  --run-preflight
```

The preflight execution is not reimplemented. The helper invokes `scripts/run_product_v1_live_demo.py --preflight-only`, preserving the canonical three-artifact readiness contract and all existing no-fake-truth/no-submit/no-send boundaries.
