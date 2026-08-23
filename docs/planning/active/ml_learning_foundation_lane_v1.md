# ML Learning Foundation Lane

Status: active parallel foundation lane
Authority: `docs/reference/search-intelligence/ml_learning_layer.md`
Branch: `feature/ml-learning-foundation`

## Delivery contract

The ML path advances in small, independently mergeable slices while deterministic Search Intelligence and the LLM booster continue to mature.

After each accepted slice:

```text
feature branch -> focused tests -> full CI -> merge to main -> rejoin main -> next slice
```

Initial slices:

1. MLF-001: pure foundation contracts and tests.
2. MLF-002: deterministic dataset manifest serialization and fingerprinting.
3. MLF-003: read-only DB-backed snapshot planning boundary.
4. MLF-004: Kaggle experiment transport contract with no model-family choice.

No slice may silently introduce ranking authority, Top-5 semantics, model-family selection, source activation, connector mutation or automatic application behavior.
