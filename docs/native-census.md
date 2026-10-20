# Native RCC Census campaign

The six public discovery adapters and three directory configurations originate
from JAP Cloud commit `c053b72228dd20b79fa3d3b9bb7df835069a94ba`.
Classic vendors them so this campaign does not depend on Cloud SQL.
The Hannover adapter retains nonlocal and unclassified employers too.
Existing Classic candidates are included in the factory population.

Bronze keeps HTTP response bytes and hashes, source payloads, identity evidence
and all observed candidates. An exact normalized company name groups observations;
conflicting websites remain visible as `IDENTITY_REVIEW`, never silently chosen.
Missing names remain in the retained source payload and rejected-row summary.
No personal geography/relevance filter is applied. Silver normalization and
Gold relevance selection are subsequent work.

The pinned `classic-census-v1` request writes migration 118's new Bronze tables.
Only after its readback proof does the finite API producer submit the required
`classic-census-factory-NN` requests. Each handles at most 100 candidates.
The initial campaign budget is 10,000 candidates, not a resource pool limit.
All candidates are still retained if that budget is exceeded; factory admission
then requires an explicit larger catalog.

Each candidate has a durable assessment intent. A previously completed result
is read; an uncertain intent stops instead of recrawling. Time limits, identity
ambiguities and unsupported structures are terminal diagnostic outcomes.
This campaign measures factory qualification, not connector activation:
`QUALIFIED` means the existing deterministic factory reports `recipe_ready`.
It is not proof of a newly harvested job or of suitability for Jens.
Source failures and partial directory observations remain explicit.

The finite producer owns no runner and never executes a workload locally.
RCC performs all collection and assessment with its native leases, queue and
isolated execution. Closing the operator terminal does not stop the producer.
It never automatically re-POSTs a request after an uncertain response.
The producer is not a recurring crawl schedule.

Tests: synthetic population and parser contracts, 1,735-candidate coverage,
API producer duplicate/lost-response behavior, and integration against
PostgreSQL session-local temporary tables. Productive rows are not modified by tests.
