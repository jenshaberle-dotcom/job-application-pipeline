# E.ON SuccessFactors Connector Slice

## Evidence

The E.ON Digital Technology corporate origin is operator-verified, while the
approved non-browser collector remains blocked on the corporate page with HTTP
403. A separate bounded feasibility probe reached the public E.ON Germany career
board on `careers.eon.com` with HTTP 200 and found one job-search page plus
concrete job-detail evidence.

The architecture therefore separates:

- employer-origin truth: the verified E.ON Digital Technology corporate URL;
- acquisition target: the public E.ON Germany recruiting board;
- collector state: blocked for the corporate page, feasible for the recruiting
  board.

## Implementation

The connector is implemented as a reusable `successfactors` source family with
`eon_germany` as the first configured target. It:

1. fetches one public listing page;
2. accepts only exact configured hosts and concrete job paths with numeric IDs;
3. excludes working-student, internship, apprenticeship, trainee, and dual-study
   titles;
4. ranks title-relevant candidates;
5. fetches at most five detail pages;
6. emits records only when the detail page identifies
   `E.ON Digital Technology GmbH`;
7. exposes a no-write live preview.

## Boundary

- no browser automation;
- no access-control bypass;
- no pagination;
- one listing request and at most five detail requests;
- no provider request;
- no database, Bronze, or Silver write;
- no source activation;
- no scheduler change;
- code-backed registry support does not create an active DB search profile;
- preview output is `review_output_only_not_pipeline_input`.

## Preview

```bash
python -m scripts.run_successfactors_connector_preview \
  --target-key eon_germany \
  --search-term "Data" \
  --max-detail-pages 5
```

The preview is a bounded live diagnostic. Productive ingestion remains closed
until a separate controlled activation slice supplies an active DB search
profile and validates Bronze-to-Silver behavior.
