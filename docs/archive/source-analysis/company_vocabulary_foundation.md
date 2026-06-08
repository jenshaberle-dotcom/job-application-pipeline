
# S5G-A Company Vocabulary Foundation

## Purpose

Company vocabulary observations make the new company-centered Search Intelligence model explicit:

```text
Exploration sources
→ companies
→ observed vocabulary
→ company-specific search strategy
→ origin validation
```

The goal is not to measure an exact false-negative rate. That is not realistically observable. Instead, this block creates measurable improvement signals:

- new vocabulary discovered
- vocabulary per known company
- exploration-source contribution to company vocabulary
- later origin confirmation of vocabulary-derived search terms
- search-term portfolio growth per company

## Scope

S5G-A only derives vocabulary from existing `market_evidence` rows. It does not create new discovery requests, does not crawl additional pages, and does not mutate search profiles.

## New table

`company_vocabulary_observations` stores lightweight vocabulary observations by company, observed term, source, and evidence type.

This is intentionally not a job table. It stores learning evidence, not Bronze job records.

## Agent

`scripts.run_company_vocabulary_agent` supports preview-first execution and explicit `--write` mode.

```bash
python -m scripts.run_company_vocabulary_agent --limit 500
python -m scripts.run_company_vocabulary_agent --limit 500 --write --reviewed-by jens
```

## Boundaries

- no search-profile mutation
- no source activation
- no connector registration
- no Bronze writes
- no scheduler changes
- no CSV/Excel/export-as-input workflow

## Follow-up

If this foundation proves useful, the next block should connect company vocabulary to a company-specific search-term portfolio instead of treating all search terms as global configuration.
