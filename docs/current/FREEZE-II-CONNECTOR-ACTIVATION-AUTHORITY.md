# Freeze-II Connector Activation Authority

status: withheld
sensor_expansion_complete: false
expanded_cohort_frozen: false
activation_allowed: false

This file is the product effect boundary for generic Employer-Origin activation. Execution is not owned by a repository-local runner workflow.

While any value above is false, any future RCC-assigned activation workload must fail closed before runtime/database access or source activation. The previous project-local activation workflow is physically absent and must not return.

Activation may be authorized only by a reviewed repository change after:

1. LinkedIn/Indeed conservative market-sensor evidence has been collected;
2. genuinely new employer/source candidates have been resolved to direct Employer-Origin/ATS sources;
3. the expanded candidate cohort has been frozen as the connector denominator; and
4. the next connector/live-search slice explicitly requires productive activation.

Historical proof-pass sources and prior successful activation runs are evidence only. They do not override the current Freeze-II sequence.
