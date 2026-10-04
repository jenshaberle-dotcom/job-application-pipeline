# Dynamic RCC validation test plans

JAP declares test content; RCC owns planning/admission and exact General-Pool execution.
`.rcc/test-management.json` is trusted only after qualification/adoption on main. It defines
full, census, factory, ML replay and RCC-contract test blocks. Suites can be combined for a
specific request; no per-company parser or runner authority is added.

For v1, `pr_validation` and `merge` require the full suite. This is intentional until measured
change-impact evidence justifies a smaller mandatory baseline. `diagnostic` is adjustable,
retains required census checks and has optional Factory/ML/RCC blocks and runs separately from automatic
PR qualification. Diagnostics cannot produce a green merge-gate status.

The PR description accepts one source-bound `rcc-test-request` JSON block with action, exact
head, `add` suite IDs and `omit` optional-suite reasons. No commands, runner selectors or secrets
are accepted. RCC determines policy from trusted main, protects required/affected tests and
binds plan identity to source, target, policy and runtime. Repeated equivalent PR/merge requests
reuse evidence; changed test coverage or context creates a new execution identity.

The optional workflow input `test_plan` invokes `run_validation_test_plan.py` extracted from
its trusted policy commit, rather than the candidate copy. The launcher verifies digests,
source/policy/runtime identity, mandatory suites and dependency order, executes approved argument
arrays without shell interpolation, and uploads a plan-bound receipt. Normal repository/documentation
contracts and changed-file Ruff still run after suite execution. Empty plan retains existing full pytest.

Rollout: qualify and merge this consumer prerequisite using the current full RCC PR workflow;
then adopt RCC's planner/catalog opt-in through its own qualified source. Installing the opt-in
first would block on missing trusted policy. No live execution or merge is implied by offline tests.
Main integration/release/experiment actions remain separate lifecycle work; public Census stays in
its separately admitted workflow.
