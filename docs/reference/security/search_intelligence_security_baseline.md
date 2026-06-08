# Search Intelligence Security Baseline

Status: active security baseline
Scope: local-first project with cloud-readiness constraints

## Purpose

Security is a first-class maturity area. The project must not rely on local-only assumptions that would break during cloud migration or productionization.

## External request boundaries

The URL Finder, evidence agents and market sensors may call external networks only under bounded policies.

Minimum controls:

- block localhost, private IP ranges and link-local targets
- block cloud metadata endpoints
- limit redirect depth
- revalidate the final redirected host
- bound connect timeout and read timeout
- bound total candidate runtime
- limit response size used for scoring
- record timeout and rejection reasons
- keep search-provider API keys in environment or secret store
- never write secrets to exports, reports or logs

## SSRF-relevant blocked target examples

The following target categories must not be probed by agent-generated URLs:

- localhost and loopback hosts
- private IPv4 ranges
- link-local addresses
- IPv6 loopback and local ranges
- cloud metadata services
- file URLs and non-HTTP schemes

## Report and export hygiene

Reports may include selected URLs, rejected URLs, titles, status codes and bounded evidence snippets. Reports must not include API keys, cookies, authorization headers, local absolute secrets paths or full raw responses from unknown hosts.

## Control Center security

The Control Center is currently local and personal-use oriented, but write actions must still follow the same architecture boundaries:

- no token typing as normal UX
- click plus confirmation for gated actions
- no destructive default actions
- active_controlled changes require explicit opt-in
- every write action must produce an audit trail

## Current maturity gap

Security controls are partly documented and partly implicit. ARCH-001 makes them explicit, but technical enforcement still needs follow-up implementation.

High-priority follow-up: EO-002F URL Finder Runtime Hardening.
