# CONNECTOR-ARTIFACT-QUERY-DETAIL-PROPAGATION-001

Status: implementation validation  
Issue: #402  
Blocked generation slice: #401  
Upstream S7N query recognition: #398 / PR #399

## Problem

The active S7N runtime recognizes bounded same-board query-parameter job-detail
URLs such as `https://careers.example.com/de?id=51980f`. The historical artifact
generator carries forward only path-based detail URLs, so accepted query evidence
would be lost before connector generation.

## Generic completion

A query-aware projection layer reuses the active S7N URL safety contract and the
existing artifact templates. It:

- preserves bounded query identifiers on the reviewed source domain;
- preserves historical path-based job-detail URLs;
- rejects tracking-only, redirect-like, empty, oversized, unrelated-host and
  generic-root URLs;
- renders accepted URLs into generated `KNOWN_DETAIL_URLS` and review docs;
- exposes query-aware entrypoints for both the standalone generator and the S6C
  approval-gated build contract.

The adapter supplies only a generic role-label precondition because persisted S7N
items already contain role-label evidence. Host, path, identifier, scope,
tracking and redirect validation remain owned by the active S7N runtime.

## Validation

Regression coverage proves:

- `/de?id=<bounded-id>` is retained;
- `/job/.../<id>/` remains retained;
- tracking and redirect queries are rejected;
- empty and oversized identifiers are rejected;
- unrelated hosts and generic career roots are rejected;
- query-only evidence renders into module and documentation content in memory.

## Boundary

This repair authorizes no:

- database mutation or build-request update;
- connector artifact write during acceptance;
- connector registration or source activation;
- Bronze, Silver or Gold mutation;
- scheduler or Wave change;
- provider or LLM request;
- company-specific control flow.

After merge, #401 must rerun an exact no-write artifact preview for Accompio and
Computacenter before any generation approval is requested.
