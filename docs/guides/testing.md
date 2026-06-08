# Testing

## Purpose

This project uses automated tests to keep reusable parsing and connector logic stable.

Unit tests should be deterministic, fast and independent of live third-party services.

Live source-analysis scripts may contact external websites, but they are not treated as unit tests.

## Dependencies

Runtime dependencies are defined in:

- `requirements.txt`

Development and test dependencies are defined in:

- `requirements-dev.txt`

`requirements-dev.txt` includes the runtime dependencies and adds test tooling such as `pytest`.

## Setup

Install runtime dependencies only:

    python -m pip install -r requirements.txt

Install development and test dependencies:

    python -m pip install -r requirements-dev.txt

## Running Tests

Run all tests:

    python -m pytest -q

Run only the StepStone result-card parser tests:

    python -m pytest tests/test_stepstone_result_cards.py -q

## Current StepStone Test Strategy

The StepStone result-card parser is tested with a local HTML fixture:

- `tests/fixtures/stepstone_result_cards_sample.html`
- `tests/test_stepstone_result_cards.py`

These tests validate parsing behavior without making live requests to StepStone.

The tests currently cover:

- result-card boundary detection
- title, company, location and detail URL extraction
- external job ID extraction
- article ID versus detail URL ID matching
- ignoring global detail links outside result cards
- preserving publication, remote, employment-type and salary UI prompt hints as raw signals

## Rule

Unit tests should be deterministic, fast and independent of live third-party services.
