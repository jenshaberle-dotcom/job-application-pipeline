# ADR-017: Prepare API-first dashboard architecture

## Status

Proposed

## Context

The project is evolving from a job ingestion pipeline into a personal job market intelligence and application workflow system.

Future users should be able to inspect source health, review relevant jobs, track application status and analyze job market trends visually.

Planned dashboard capabilities include:

- source monitoring with health indicators
- top daily job recommendations
- application workflow status tracking
- new relevant jobs since the last run
- historical job availability trends
- source and role-family distribution charts
- skill and role heatmaps

A local dashboard would be possible with tools such as Streamlit.

However, the long-term product vision benefits from a clearer separation between:

- data pipeline
- database views
- backend API
- frontend application
- user workflow state

## Decision

The project will prepare for an API-first dashboard architecture.

The preferred future architecture is:

- PostgreSQL for persisted data and analytical views
- FastAPI as backend/API layer
- React as frontend/UI layer
- Docker-based local development
- optional later cloud deployment

The dashboard implementation is intentionally deferred until the core data model is more stable.

Before building the UI, the project should prepare stable database concepts and views for:

- source health
- job lifecycle
- relevant job candidates
- application status
- source and role-family distributions
- skill and requirement analytics

## Consequences

The project avoids prematurely building a UI on unstable raw tables.

Frontend components can later consume stable API endpoints instead of directly depending on internal database tables.

The architecture remains suitable for a local portfolio project while preserving a path toward a cloud/web application.

This decision increases initial planning effort but reduces later rework when visualizations and workflow interactions are introduced.

## Deferred Implementation

The following components are not implemented yet:

- FastAPI backend
- React frontend
- authentication
- user management
- cloud deployment
- application status editing UI

These should be introduced only after lifecycle, relevance and Gold-layer views are stable.
