# Source Capabilities

This document compares job source capabilities.

The goal is not to force all sources into the same technical behavior.

The goal is to make source differences explicit and comparable.

## Capability Matrix

| Source | Type | Keyword | Location | Radius | Employment Type | Remote | Pagination | Full Fetch | Current Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Bundesagentur für Arbeit | Public job API | yes | yes | yes | yes | no | yes | no | implemented |
| Greenhouse | ATS job board | no | no | no | no | no | no | yes | implemented |
| StepStone | Commercial job portal | yes | yes | likely | unclear | unclear | yes | no | prepared |
| Workday | Enterprise ATS | limited | limited | no | limited | unclear | yes | no/limited | candidate |
| Personio | ATS / company career system | limited | limited | no | limited | unclear | limited | yes/limited | candidate |
| Lever | ATS job board | no/limited | limited | no | no | no | no/limited | yes | candidate |
| Company career pages | Direct employer source | variable | variable | variable | variable | variable | variable | variable | candidate |

## Source Categories

### Search-capable APIs

These sources can apply a large part of the canonical search intent server-side.

Example:

- Bundesagentur für Arbeit

### Full-fetch ATS boards

These sources expose all jobs for one company or board.

Example:

- Greenhouse

These require local filtering if the project wants only jobs matching a role term such as `Data Engineer`.

### Commercial job portals

These sources are realistic and valuable, but may involve higher technical and legal complexity.

Examples:

- StepStone
- Indeed-like platforms
- LinkedIn-like platforms

They should be isolated behind connector boundaries and implemented cautiously.

## Architectural Rule

All connectors receive the same canonical search intent.

Each connector declares which filters it can apply server-side.

Unsupported filters are applied locally where feasible.
