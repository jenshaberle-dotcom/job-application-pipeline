# ADR-032: Use Jinja2 as the Control Center Template Layer

Status: Superseded

## Decision disposition

Jinja2 was the intermediate server-rendered presentation choice. The implemented product
surface is now React/TypeScript in `frontend/control-center/`, served by the local Python
product API and presented by WebView2. The old UI choice is not current implementation authority.

The surviving boundary is presentation-only: UI/templates do not own gate, lifecycle,
source-health, ranking or application decisions. See `docs/current/architecture.md` and
`docs/reference/documentation/design_rules.md`. Original rationale remains in Git history.
