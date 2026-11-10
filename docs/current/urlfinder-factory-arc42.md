# URL-Finder and Connector Factory — arc42 supplement

Status: implementation candidate reviewed 2026-11-07; source publication and
production admission pending. Supplements [architecture](architecture.md),
not a new product UI. See [exact integration evidence](URLFINDER-SOURCE-INTEGRATION.md).

## 1. Goals and stakeholders

Jens owns product intent and acceptance. Christina needs employer-origin SOCIAL
jobs in Hannover/Region or fully remote. The portal discovery target is at least
90% correct autonomous assignments; the connector target is 95% after its eligible
denominator is defined. Neither target is established by the current samples.

## 2. Constraints

No Windows full access. Preserve Classic 1.2.7 appearance and behavior. Secrets,
private candidate facts and raw operational datasets remain outside public code.
Source merge, runtime deployment and user acceptance are separate decisions.

## 3. Context

Census and market sensors identify employers with source metadata. Employer
websites and delegated ATS provide jobs. Directories and optional search/model
providers propose URLs; they do not establish ownership. RCC supplies bounded
execution, resources and isolation. GitHub stores reviewed source history.

## 4. Solution strategy

Reuse observed URLs, redirects, links, widgets and retained bodies first. Keep
source provenance; group ATS families; verify publisher identity and exact tenant
independently. Reuse the factory compiler and finite family parsers. Separate
concrete vacancies from unsolicited applications, missing evidence and empty feeds.

## 5. Building blocks

JAP owns sensors, employer identity, URL selection, parsers, factory recipes,
profile relevance and UI read models. RCC owns demand, leases, fencing, isolation,
quarantine and execution evidence. The consumer result contract joins them.
See C2/C3 in [system diagrams](system-diagrams.md#url-finder-and-factory-integration).
Shared candidate rules live in `src/connectors/portal_discovery/` and reuse
`src/connectors/connector_factory.py`; there is no copied second compiler.

## 6. Runtime view

Sensor → employer candidate → URL candidate → independent publisher/tenant proof
→ portal content → concrete job proof → inactive recipe → separate registration
and RCC execution → Bronze/Silver/assessment → Classic read model.
The latest field observations were operator research, not broker dispatch.
An error or exhausted budget remains unresolved. Replay preserves observation
timestamps and cannot refresh job freshness. Production promotion stays explicit.

## 7. Deployment view

Windows hosts the Classic shell and bounded operator package. WSL holds separate
source checkouts, immutable runtimes and production services. Source integration
here changes only a local review copy. Production runtime identity must be read
back independently of a Git branch or GUI version file.

## 8. Crosscutting concepts

Provenance records first discovery and supporting steps separately: sensor,
census, directory, deterministic navigation, Tavily, Codex. Measure attempts,
accepted evidence, residual failures, latency and marginal success per stage.
Never silently merge employers from a shared hostname or ambiguous alias.
Transport is bounded and read-only; no provider access is enabled by code import.
Version JAP logic, RCC execution, interface contracts and desktop separately.

## 9. Decisions

[ADR-038](../decisions/adr/038_reconcile_portal_evidence_and_factory_sources.md)
complements ADR-026, ADR-035, ADR-036 and ADR-037. It remains proposed until
reviewed; existing production authority is not inferred from its presence.

## 10. Quality requirements

Keep a frozen, reproducible denominator and representative held-out evaluation.
Current campaign total: 3380 source records, not deduplicated legal entities.
Targeted field cohort: 260 records / 290 targets; 24 portal evidence candidates,
19 candidate recipes with concrete job samples. Do not extrapolate to 90%.
Check false-positive identity, tenant mismatch, empty feeds, generic applications,
partial pagination, timestamps, repeatability and profile isolation.

## 11. Risks and technical debt

RCC authenticated source read and remote publication are unverified. Historical
maintenance changes outside this URL-Finder slice still need source reconciliation.
First-party career HTML and Connectoor remain coverage gaps. The TECH PoC is not
SOCIAL production admission. Its optional live transport is not the RCC transport
contract. Daily full-chain delivery is not accepted. Namespace isolation and
single-host fixture success are not fleet or cloud scaling proof.

## 12. Glossary

Candidate: unadmitted hypothesis. Portal evidence: publisher and tenant binding
with retained content. Recipe: reusable connector definition. Job proof: a concrete
vacancy with details from its employer source. Admission: authorized production
execution. Replay: re-evaluation of old evidence, not a fresh observation.
