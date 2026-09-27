# Job-first Census source access qualification

Status: ACTIVE — 2026-09-27

Membership in the Employer Discovery Census cohort is a product decision, not
automation authority. Direct access is admitted source-by-source only after the
public access surface, terms/robots posture, and technical path are qualified.

## Current authority

| Source | Census cohort | Direct automation | Reason |
| --- | --- | --- | --- |
| Bundesagentur für Arbeit | yes | AUTHORIZED | Existing registered API connector |
| StepStone | yes | AUTHORIZED | Existing bounded result-card connector |
| GoodJobs (goodjobs.eu) | yes | WITHHELD | Active board, but direct automation has no explicit authority yet |
| XING Jobs | yes | WITHHELD | Direct automation requires a XING-authorized interface; public job-search retrieval API not established |
| meinestadt.de | yes | WITHHELD | Public terms explicitly prohibit scraping or comparable techniques |
| get in IT | yes | WITHHELD | Public user terms prohibit automated queries without explicit consent |
| jobvector | yes | WITHHELD | Automated exchange requires an explicit interface/permission path; unauthorized third-party crawling/publication is not authority |

## GoodJobs correction

The intended source is **GoodJobs at goodjobs.eu**. The prior Census key
`gutejobs` was ambiguous and pointed at the wrong domain identity. The current
`gutejobs.de` domain is not the active board used by this strategy.

GoodJobs remains useful as a comparison source, but direct automated acquisition
is withheld until an explicitly permitted access path exists. Publicly visible
terms describe website use by natural persons, restrict use to the intended
purpose, and reserve rights in website/database content. JAP therefore does not
treat public readability as automation permission.

## Flight rule

The first Census flight may execute only sources whose qualification is
`authorized`. A source can remain in `CORE_SENSORS` while its direct
automation status is `withheld` or `pending_review`.

This separation is deliberate: no anti-bot bypass, no inferred permission, and no
platform-specific acquisition path may become authority merely because a board is
strategically valuable.


## Reviewed direct-access outcomes

The 2026-09-27 public-access review did not authorize another direct connector.
XING, meinestadt.de, get in IT, and jobvector remain useful comparison boards,
but each exposes terms or interface boundaries that make unapproved direct
automation inappropriate. This does not remove them from market coverage:
their evidence may later enter through an explicitly permitted interface,
provider-authorized feed, or separately qualified external-index transport.

No source may be silently upgraded from `withheld` to `authorized` merely
because its pages are publicly readable or indexed by a search engine.
