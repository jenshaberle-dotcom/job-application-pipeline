# E.ON Extensive Experience Evidence Fix 001A

Status: implementation for issue `#359`

## Runtime finding

The first private plan-only run after migration 087 stopped with:

`stored E.ON description does not explicitly evidence several years of professional experience`

Migration 087 itself applied cleanly and was fully tracked. The stop occurred before any assessment update or revision insert.

## Root cause

The deterministic parser accepted only numeric or explicitly multi-year formulations such as `several years of professional experience`.

The stored E.ON employer-origin description instead uses the strong qualitative requirement:

`Extensive professional experience in data engineering positions and a consulting background`

This is explicit senior-level requirements evidence, but it is not a numeric years statement. Rejecting it discarded available employer-origin evidence.

## Bounded correction

The seniority parser additionally accepts the exact semantic class:

`extensive [relevant] professional experience`

The correction does not accept generic `professional experience`, `initial experience`, title-only evidence or capability claims.

## Preserved boundaries

- no numeric years are inferred;
- `requirements_seniority` may become `senior` from the explicit extensive-experience requirement;
- `capability_fit_status` remains `unknown`;
- weekly hours remain unknown;
- no score is generated;
- no hard-filter pass is forced;
- no network, provider or LLM request is added;
- migration 087 and its applied checksum remain unchanged.

## Runtime continuation

After merge, rerun the existing plan-only, Apply and replay commands. Migration status should already show 87 tracked migrations and zero pending migrations.