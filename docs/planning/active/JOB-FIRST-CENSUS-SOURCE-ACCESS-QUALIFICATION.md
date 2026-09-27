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
| XING Jobs | yes | PENDING REVIEW | Terms/robots/technical path not yet qualified |
| meinestadt.de | yes | PENDING REVIEW | Terms/robots/technical path not yet qualified |
| get in IT | yes | PENDING REVIEW | Terms/robots/technical path not yet qualified |
| jobvector | yes | PENDING REVIEW | Terms/robots/technical path not yet qualified |

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
