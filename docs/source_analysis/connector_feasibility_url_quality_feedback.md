# S7N Connector Feasibility URL Quality Feedback

## Purpose

S7N must not silently convert a bad persisted origin URL into a generic manual-review result. If Origin Source Discovery or manual URL assignment selected a URL and the bounded feasibility probe later finds that the URL is technically wrong, too noisy or not probe-ready, that result is learning feedback for the Origin Source Discovery loop.

## Feedback Loop

```text
Origin URL selected
→ Connector Feasibility Probe
→ URL quality feedback
→ Origin Source Discovery reassessment / manual URL repair
→ Connector Build Planning only after structural job evidence exists
```

## Evidence Types

Accepted evidence is split deliberately:

- `job_search_page_evidence` — a bounded, public, career/job search page that is useful for connector build planning.
- `job_detail_candidate_evidence` — a job/detail-like URL or link label that can support connector build planning.
- `career_context_evidence` — career context such as students, pupils, Ausbildung or generic career pages. Useful context, but not enough for connector build planning by itself.

Rejected evidence is kept as structured feedback:

- `technical_or_legacy_noise` — assets, feeds, oEmbed, `wp-json`, non-production/test/release URLs or non-HTTPS technical links.
- `offsite_social_noise` — social profile links such as Facebook or Instagram.
- `marketing_or_press_noise` — root homepage, press/media/download/legal/about/contact navigation.
- `aggregator_noise` — StepStone, LinkedIn, XING, Indeed, Glassdoor and similar market evidence domains.

## Feedback Codes

- `origin_url_not_reachable` — selected URL could not be reached by the bounded probe.
- `origin_url_repair_candidate_detected` — selected URL failed, but the response exposed a plausible alternative career/job URL.
- `origin_url_asset_noise_only` — selected URL is reachable, but detected links are assets, feeds, technical endpoints or external noise.
- `origin_url_has_career_page_but_no_job_structure` — selected URL looks career-like, but no structural job evidence was detected.
- `sample_job_evidence_found` — selected URL is reachable and exposes structural job evidence.

## Connector-Build Boundary

`likely_feasible` requires structural job evidence. A reachable website is not enough. Favicons, logos, feeds, WordPress `wp-json` endpoints, oEmbed links, CSS, JS, media assets, social links, root homepages, press pages and generic Schüler/Student/Ausbildung links are explicitly not sample job evidence.

This keeps the product from turning URL assignment into optimistic connector generation. The agent chain must learn from weak URL assignments instead of hiding them behind generic manual-review output.
