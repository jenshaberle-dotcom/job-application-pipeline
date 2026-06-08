# S5G-C Search-Term Value Foundation

## Purpose

S5G-C turns raw company vocabulary observations into candidate-specific search-term value signals.

S5G-A intentionally records observed vocabulary without judging it. That means useful terms such as `analytics`, `platform` or `cloud` can sit next to noisy tokens such as `mitarbeiter`, `services` or `genders`.

S5G-B added the first explicit candidate profile for Jens' Data Engineer transition. S5G-C combines both streams:

```text
Company Vocabulary
+
Candidate Intelligence
=
Search-Term Value
```

## Boundary

This block does not mutate search profiles, activate sources, register connectors, write Bronze jobs or change scheduler behavior.

The output is scoring evidence only.

## Tables

### vocabulary_signal_scores

Aggregates raw vocabulary by observed term:

- how many companies contributed the term
- how often it was observed
- how much noise penalty applies
- the resulting signal score

### search_term_value_scores

Combines the vocabulary signal with Jens' candidate profile:

- vocabulary signal score
- career-direction score
- current capability alignment
- growth-gap signal
- overall value score
- value band

## Interpretation

A high-frequency term is not automatically valuable.

A valuable term is one that combines:

- market/exploration signal
- fit to Jens' Data Engineer direction
- enough relevance to justify later trial or portfolio handling

## Next step

S5H should build on this foundation with capability-gap analysis from actual job evidence. Search-term value is not a job-fit score yet; it is a bridge between vocabulary discovery and candidate-specific market direction.
