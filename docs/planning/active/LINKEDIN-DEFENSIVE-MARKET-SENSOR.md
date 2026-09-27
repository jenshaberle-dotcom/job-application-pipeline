# LinkedIn Defensive Market Sensor — Freeze-II Research & Authority

Status: ACTIVE DESIGN AUTHORITY
Reviewed: 2026-09-27
Scope: JAP Classic Freeze-II S0.5/S0.6
Purpose: discover employer/source candidates with the lowest practical LinkedIn legal/operational attack surface.

This document is an engineering risk-minimisation record, not legal advice. A commercial/public deployment should still receive counsel review.

## Decision

JAP may use LinkedIn only as a **defensive discovery/freshness sensor**.

The production-authoritative path is:

`approved external search index -> transient LinkedIn result metadata -> minimal derived company signal -> raw platform metadata discarded -> direct employer/ATS resolution -> normal Employer-Origin proof`

LinkedIn is never:

- an ingestion connector;
- a Bronze/Silver/Product job source;
- a job-detail source;
- an application/submission surface;
- a member/profile/recruiter data source;
- a source of persistent raw job descriptions, snippets, titles, URLs or LinkedIn job identifiers.

## Why this boundary is stricter than "public page = safe"

### LinkedIn's current contractual/technical position

Reviewed sources:

- LinkedIn User Agreement, effective 2025-11-03:
  https://www.linkedin.com/legal/user-agreement
- LinkedIn Crawling Terms:
  https://www.linkedin.com/legal/crawling-terms
- LinkedIn robots.txt:
  https://www.linkedin.com/robots.txt
- LinkedIn Help — Prohibited software and extensions:
  https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions
- LinkedIn Help — Automated activity:
  https://www.linkedin.com/help/linkedin/answer/a1340567/automated-activity-on-linkedin
- LinkedIn Jobs Terms:
  https://www.linkedin.com/legal/jobs-terms-conditions

Material observations:

1. LinkedIn's User Agreement prohibits software/scripts/robots used to scrape or copy the Services and prohibits bypassing access controls/use limits.
2. The User Agreement also addresses information obtained indirectly through third parties such as search tools/data aggregators. Therefore an external search provider lowers JAP's direct-access exposure but does **not** make LinkedIn-derived evidence contract-risk-free.
3. LinkedIn's Crawling Terms say automated crawling/indexing requires express permission.
4. LinkedIn's robots.txt begins with an express notice that automated access without permission is prohibited. It also disallows multiple job/search/guest/API paths for major crawlers.
5. LinkedIn publicly states that third-party scraping/automation tools can violate its User Agreement and can lead to account restriction.

Engineering consequence: JAP must not treat "public", "guest", "no login", "third-party scraper" or "search indexed" as equivalent to platform permission.

### hiQ does not create a general scraping safe harbour

Reviewed sources:

- Ninth Circuit 2022 opinion:
  https://law.justia.com/cases/federal/appellate-courts/ca9/17-16783/17-16783-2022-04-18.html
- District docket / permanent injunction:
  https://dockets.justia.com/docket/california/candce/3%3A2017cv03301/312704
- LinkedIn case statement:
  https://news.linkedin.com/2022/november/court-order-affirms-linkedin-s-legal-positions-against-hiq-in-da

The Ninth Circuit decision addressed a preliminary-injunction/CFAA question around publicly available profile access. It did not establish a general rule that LinkedIn scraping is lawful. The later district-court proceedings and consent judgment ended with a permanent injunction against hiQ. JAP therefore does not use hiQ as authority for a direct scraper.

## Open-source operational evidence

The public ecosystem strongly separates "works technically" from "low-risk/reliable".

### Unofficial Voyager/account automation — RED for JAP

Examples reviewed:

- tomquirk/linkedin-api family / mirrors:
  https://github.com/tomquirk/linkedin-api
- transitive-bullshit/linkedin-api:
  https://github.com/transitive-bullshit/linkedin-api
- EseToni/open-linkedin-api:
  https://github.com/EseToni/open-linkedin-api

Common mechanics include regular-account credentials, authenticated cookies, LinkedIn Voyager endpoints, throttling, proxies and challenge/CAPTCHA recovery. The projects themselves warn about User Agreement violations, bans/restrictions or challenges.

JAP must not adopt these mechanics.

### Direct automated HTTP is operationally brittle — RED for JAP

Evidence reviewed:

- Sherlock issue #2652:
  https://github.com/sherlock-project/sherlock/issues/2652
  - reports LinkedIn HTTP 999 for automated requests and proposes disabling/deprecating LinkedIn detection.
- OpenClaw issue #59849:
  https://github.com/openclaw/openclaw/issues/59849
  - reports LinkedIn login/bot-detection problems from datacenter/VPS browser automation.

JAP interpretation: anti-bot pressure is a stop signal, not a prompt to add residential proxies or evasion.

### Managed third-party scrapers — AMBER, not Core authority

Examples exist that route LinkedIn scraping through Apify/other managed infrastructure and advertise no-login/public search. Some job-automation projects keep such integrations optional rather than core.

Relevant example:
- career-ops issue #791:
  https://github.com/career-ops-hq/career-ops/issues/791

JAP interpretation: outsourcing scraping may reduce operational blocking of JAP's own IP/account but does not remove LinkedIn contractual/data-use risk. Managed scrapers therefore require a separate operator/legal review and are not admitted into the core sensor path.

## Official API lane

Reviewed:

- LinkedIn API access overview:
  https://learn.microsoft.com/linkedin/shared/authentication/getting-access
- Talent Solutions Job Posting API:
  https://learn.microsoft.com/linkedin/talent/job-postings/api/overview

LinkedIn supports official APIs, but most permissions/programs require explicit approval/partner access. The Job Posting API is oriented to authorized posting/integration, not a generally open job-search feed.

Authority:
- if LinkedIn grants JAP explicit written/API permission for a suitable discovery endpoint, that official path becomes preferred;
- until then, no unofficial API may impersonate an official API.

## EU/GDPR minimisation

Reviewed:

- EDPB web-scraping guidance/news (2026):
  https://www.edpb.europa.eu/news/edpb-sheds-light-on-anonymisation-and-web-scraping-for-generative-ai-and-adopts-final-version_en
- CNIL data collection/scraping guidance:
  https://cnil-d10.cnil.fr/en/data-protection-in-data-collection-management
- CNIL legitimate-interest scraping measures:
  https://www.cnil.fr/fr/node/165906

Although JAP's target is employer/job-market evidence rather than member profiling, provider snippets can incidentally contain personal data. The sensor therefore applies minimisation before persistence.

## JAP admissibility matrix

### GREEN — current Core path

- operator-triggered or separately reviewed low-frequency run;
- approved external search-index provider;
- site-bounded query for public LinkedIn job-result references;
- no request from JAP to linkedin.com;
- no account, cookie, token or browser session;
- no member/profile path;
- no CAPTCHA handling;
- no proxy rotation/evasion;
- raw provider URL/title/snippet used transiently only;
- persist only:
  - platform name;
  - provider;
  - JAP-owned query/search intent;
  - observed company signal;
  - company-signal extraction rule/status;
  - requested/coarse location signal;
  - observation timestamp;
  - one-way SHA-256 reference hash;
- raw platform URL/title/snippet persistence = 0;
- direct employer/ATS resolution required before candidate/source proof;
- LinkedIn evidence never becomes Product job truth.

This is **lower risk, not zero risk** because LinkedIn's User Agreement also addresses data obtained through third-party search/data tools.

### AMBER — separate review required

- official LinkedIn API requiring partner approval;
- managed scraping/API provider that itself retrieves LinkedIn data;
- recurring automated cadence;
- persistence of additional LinkedIn-derived fields;
- any user-facing display of LinkedIn-derived content.

No AMBER mechanism may silently become Core.

### RED — prohibited

- direct automated HTTP to linkedin.com;
- LinkedIn `/voyager/api`;
- guest/internal job APIs such as `/jobs-guest/`;
- automated login or stored LinkedIn credentials/cookies;
- Selenium/Playwright/browser automation against LinkedIn;
- CAPTCHA solving/bypass;
- residential/datacenter proxy rotation intended to defeat blocks;
- fake/throwaway accounts;
- request fingerprint or User-Agent disguise;
- member/profile scraping;
- recruiter/person/contact extraction;
- raw LinkedIn job-description persistence;
- persistent LinkedIn job URLs/job IDs as source identity;
- using LinkedIn evidence directly for Bronze/Silver/Product/ranking/application authority.

## Persistence & retention

For the S0.5 sensor artifact:

- raw LinkedIn URL persistence: 0;
- raw LinkedIn title persistence: 0;
- raw LinkedIn snippet persistence: 0;
- raw job-description persistence: 0;
- member/recruiter personal-data targeting: 0;
- artifact retention: 3 days;
- candidate/source DB writes in the sensor run: 0.

The S0.6 review may persist only the minimal derived company evidence needed for known-candidate suppression and direct Employer-Origin resolution.

## Cadence

Current authority remains **no scheduled LinkedIn polling**. S0.5 is operator-triggered.

Any recurring schedule requires a separate reviewed change. Default future design target, if admitted, is no more than one bounded market-sensor sweep per day, with explicit request/result budgets and no adaptive retry escalation.

Zero yield and provider-unavailable are valid outcomes.

## Fail-closed / kill switches

Disable the LinkedIn sensor rather than escalate access if any of the following occurs:

- LinkedIn sends a cease-and-desist, complaint or explicit access objection;
- current terms/robots/crawling rules become materially stricter for the admitted path;
- the search provider begins requiring LinkedIn credentials, cookies, CAPTCHA solving, proxies or bypass features;
- provider results expose member/profile/recruiter personal data beyond incidental transient text;
- the provider cannot identify its data provenance or terms sufficiently for review;
- repeated runs require higher request rates to remain useful;
- the sensor is proposed as Product job authority instead of employer-discovery evidence.

## Freeze-II consequence

The S0.5/S0.6 sequence remains:

`search-index LinkedIn signal -> minimal derived company evidence -> known-candidate suppression -> direct employer/ATS resolution -> reviewed candidate promotion -> expanded-cohort freeze`

The LinkedIn reference is discarded before Origin learning. Employer-Origin remains the only normal job/source authority.
