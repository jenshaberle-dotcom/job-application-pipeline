# ML-PILOT-001B runtime status evidence

The one-shot runtime DB status workflow persists only allowlisted aggregate migration metadata to the ML-PILOT-001B PR discussion so later re-entry can determine whether the label schema is actually present.

The status probe is read-only. It does not apply migrations, write labels, train models, call providers, mutate ranking, or create product authority.
