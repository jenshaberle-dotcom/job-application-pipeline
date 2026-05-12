# StepStone Source Analysis

## Status

Prepared for evaluation.

No production connector has been implemented yet.

## Purpose

This document evaluates StepStone as a potential job data source for the job application pipeline.

The goal is to understand whether StepStone can be integrated responsibly and technically cleanly before implementing a connector.

This is intentionally not a connector implementation document.

It documents source behavior, risks, open questions and a possible connector path.

---

## Current Repository State

A StepStone connector skeleton exists in:

```text
src/connectors/stepstone.py
