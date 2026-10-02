# JAP Classic product

Status: current product summary. Project character: **A — Intent Locked**.

JAP supports evidence-based job discovery, assessment, review and application preparation.
Jens owns desired behavior. The [product contract](../reference/product-contract/README.md),
accepted decisions and approved private Candidate Facts govern intent; open PRD decisions
remain open only where a later accepted contract has not resolved them.

## Operator journey

1. Discover employers and search spaces through bounded market sensors.
2. Verify direct Employer-Origin/ATS evidence and controlled connector readiness.
3. Acquire raw jobs into Bronze and derive canonical Silver jobs.
4. Explain requirements and Candidate Fit using approved private facts.
5. Apply normal hard filters and ranking; show authoritative Top 5.
6. Prepare CV/letter drafts from approved templates and evidence, then track application outcomes.

Candidate Fit and Affinity remain separate. There is no approved combined-score shortcut.
Missing evidence must stay visible; employer-specific patches and direct Top-5 writes cannot
replace normal product gates. The generic assessment cohort's 10 evaluated / 5 Top-5 targets
are a validation contract, not proof that the current database satisfies it.

## Implementation and limits

The current UI is React. The Windows WebView2 host runs the local product through WSL and
PostgreSQL. Private profiles, CVs, mail evidence and credentials stay in the private runtime;
release bundles do not contain them. Application drafting uses the code-defined provider and
authentication contract; model upgrades in open PRs are not shipped behavior.

Preparing a draft or tracking an outcome does not authorize sending an application.
Source activation, recurring execution, provider spend and ranking mutation retain their own
effect boundaries. In particular, [Freeze-II activation restrictions](FREEZE-II-CONNECTOR-ACTIVATION-AUTHORITY.md)
constrain the standing [A1 connector policy](connector_autonomy_policy.md).

## Cloud direction

Classic supplies reusable product contracts, code and real migration evidence. Cloud parity
and migration acceptance precede the switch to the sole normal Cloud runtime. During that
transition, maintaining the installed Classic product does not justify a second independent
feature roadmap. See [ADR-034](../decisions/adr/034_define_shared_jap_product_and_runtime_coexistence.md).
