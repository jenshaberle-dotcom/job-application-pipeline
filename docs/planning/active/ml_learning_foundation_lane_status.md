# ML Learning Foundation Lane Status

Status: MLF-002 candidate slice
Authority: `docs/planning/active/ml_learning_foundation_lane.md`

Current candidate:

- MLF-002 — deterministic dataset manifest serialization and fingerprinting.
- Scope remains side-effect-free: no DB reads/writes, no Kaggle API calls, no model training and no productive inference.
- Merge condition: focused manifest tests plus full repository CI green.

After merge, `feature/ml-learning-foundation` must rejoin the resulting `main` before MLF-003 starts.
