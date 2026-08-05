# E.ON Flattened Requirement Segmentation 001A

Status: implementation for Issue `#371`

## Runtime finding

The exact private heading diagnostic on raw job `26342` / Silver job `466` returned one normalized line containing the complete E.ON page text. The stored description therefore preserves the employer wording but not its original HTML or block boundaries.

The prior profile-heading failures were segmentation failures, not missing evidence and not Unicode-heading failures.

## Exact fallback contract

The fallback is used only by the exact E.ON requirement inventory runner.

It activates only when the description normalizes to one long line and then requires:

- exactly one `Your Profile – authentic & open-minded` anchor;
- exactly one `Our Benefits – smart & useful` anchor;
- the profile anchor before the benefits anchor;
- an exact profile body equal to the eight employer statements observed in the private read-only diagnostic;
- the same statement order and no additional text.

The eight statements are preserved verbatim after whitespace normalization. The fallback reconstructs temporary block boundaries only so the existing inventory parser can assign stable statement identities and lexical families.

Structured HTML or multi-block descriptions remain unchanged.

## Fail-closed behavior

The fallback rejects:

- short single-line inputs;
- missing or duplicate anchors;
- reversed anchors;
- missing statements;
- reordered statements;
- additional inferred or unobserved text;
- any profile-body wording drift.

It does not guess sentence boundaries, use fuzzy matching, infer skills or call an LLM.

## Hash and evidence truth

`description_sha256` continues to fingerprint the complete original stored description. The reconstructed block representation is an internal parsing aid only and is never reported as the source description fingerprint.

Statement keys and `section_sha256` remain derived from the exact projected employer statements.

## Preserved boundaries

- PostgreSQL transaction remains read-only;
- zero database writes;
- zero Candidate Fact reads or writes;
- no capability-fit decision;
- no assessment, readiness, ranking or Top-5 mutation;
- no weekly-hours inference;
- no provider, LLM or network call;
- no source, connector or scheduler activation;
- no application action.

## Completion condition

Issue `#371` and the parent inventory issues remain open until the exact private requirement inventory replay produces eight statements with zero side effects.
