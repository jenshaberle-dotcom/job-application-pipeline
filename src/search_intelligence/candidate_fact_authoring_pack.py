from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
from typing import Any, Final, Mapping

from src.search_intelligence.candidate_fact_profile import (
    PROFILE_KEY,
    SCHEMA_VERSION,
    parse_candidate_fact_profile,
)
from src.search_intelligence.eon_requirement_tag_mapping import _EXACT_SPECS


AUTHORING_PACK_SCHEMA: Final = "candidate_fact_authoring_pack.v1"
WORKBOOK_SCHEMA: Final = "eon_candidate_fact_authoring_workbook.v1"
OVERWRITE_TOKEN: Final = "CANDIDATE-FACT-AUTHORING-PACK-OVERWRITE-001"

PROFILE_FILENAME: Final = "candidate_fact_profile.private.json"
WORKBOOK_FILENAME: Final = "eon_candidate_fact_authoring_workbook.private.json"
README_FILENAME: Final = "README.private.md"

EON_DESCRIPTION_SHA256: Final = (
    "ee2498caa5c374f0b3740030213391b7a73a91b27e00e0de396c16ee963d3a8a"
)
EON_SECTION_SHA256: Final = (
    "d4dcbd0714c68fc356e8b25fd677e686854fa36999d528134feb1e2a78f5ad40"
)
EON_TAG_MAP_SHA256: Final = (
    "3a49b958d433d452c60b8167595345e9581e056c58526ddfc2a26e063356b856"
)

_PROFILE_VERSION_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")


@dataclass(frozen=True)
class CandidateFactAuthoringPack:
    output_dir: Path
    profile_path: Path
    workbook_path: Path
    readme_path: Path
    statement_count: int
    unique_tag_count: int
    profile_version: str

    def canonical_summary(self) -> dict[str, Any]:
        return {
            "schema_version": AUTHORING_PACK_SCHEMA,
            "output_dir": str(self.output_dir),
            "profile_path": str(self.profile_path),
            "workbook_path": str(self.workbook_path),
            "readme_path": str(self.readme_path),
            "statement_count": self.statement_count,
            "unique_tag_count": self.unique_tag_count,
            "profile_version": self.profile_version,
            "candidate_fact_statements_generated": 0,
            "provenance_references_generated": 0,
            "capability_claims_inferred": 0,
        }


def _normalize_profile_version(value: str) -> str:
    result = value.strip().casefold()
    if _PROFILE_VERSION_RE.fullmatch(result) is None:
        raise ValueError(
            "profile_version must be 3-128 lowercase characters using only "
            "letters, digits, dot, underscore or hyphen"
        )
    return result


def build_empty_draft_profile(*, profile_version: str) -> dict[str, Any]:
    normalized_version = _normalize_profile_version(profile_version)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "profile_key": PROFILE_KEY,
        "profile_version": normalized_version,
        "status": "draft",
        "approved_by": None,
        "approved_at": None,
        "facts": [],
    }
    profile = parse_candidate_fact_profile(payload)
    if profile.status != "draft" or profile.facts:
        raise AssertionError("generated Candidate Fact profile is not an empty draft")
    return payload


def build_eon_authoring_workbook(*, profile_version: str) -> dict[str, Any]:
    normalized_version = _normalize_profile_version(profile_version)
    requirements: list[dict[str, Any]] = []
    all_tags: set[str] = set()

    for order, spec in enumerate(_EXACT_SPECS, start=1):
        all_tags.update(spec.tags)
        requirements.append(
            {
                "order": order,
                "statement_key": spec.statement_key,
                "employer_statement": spec.text,
                "source_expectation_class": "profile_statement",
                "obligation_strength": "unspecified",
                "canonical_employer_tags": list(spec.tags),
                "operator_review": {
                    "evidence_decision": "unreviewed",
                    "candidate_fact_keys": [],
                    "private_notes": "",
                },
            }
        )

    if len(requirements) != 8:
        raise AssertionError("authoring workbook expects exactly eight E.ON statements")
    if len(all_tags) != 26:
        raise AssertionError("authoring workbook expects exactly 26 E.ON tags")

    return {
        "schema_version": WORKBOOK_SCHEMA,
        "review_output_only_not_pipeline_input": True,
        "candidate_truth_state": "not_authored",
        "profile_version_target": normalized_version,
        "source_binding": {
            "raw_job_id": 26342,
            "silver_job_id": 466,
            "description_sha256": EON_DESCRIPTION_SHA256,
            "section_sha256": EON_SECTION_SHA256,
            "tag_map_sha256": EON_TAG_MAP_SHA256,
            "statement_count": len(requirements),
            "unique_tag_count": len(all_tags),
        },
        "instructions": {
            "employer_tags_are_candidate_truth": False,
            "automatic_personal_fact_extraction_allowed": False,
            "operator_must_author_every_candidate_fact": True,
            "operator_must_supply_provenance": True,
            "operator_must_approve_before_apply": True,
            "target_directions_are_capability_evidence": False,
            "planned_capabilities_are_capability_evidence": False,
        },
        "requirements": requirements,
    }


def build_private_readme(*, profile_version: str) -> str:
    normalized_version = _normalize_profile_version(profile_version)
    return f"""# Private Candidate Fact authoring pack

This directory is private runtime state and must remain outside version control.

Target profile version: `{normalized_version}`

## Files

- `{PROFILE_FILENAME}` is an importable but empty `candidate_fact_profile.v1` draft.
- `{WORKBOOK_FILENAME}` is a review worksheet only. It is not pipeline input.
- `{README_FILENAME}` is this operating guide.

## Guided authoring

Do not edit the nested JSON files directly during the normal operator workflow.
Start the local guided assistant instead:

```bash
.venv/bin/python -m scripts.author_private_candidate_facts
```

The assistant presents each of the eight E.ON statements and its employer tags as prompts,
requires an explicit operator decision, validates every manually authored fact through the
existing schema, and writes only after the exact confirmation token `SPEICHERN`.

- `q`, EOF or interruption exits without changing either private file.
- Confirmed changes create timestamped backups beneath `private_candidate_facts/backups/`.
- New facts remain `proposed`; the profile remains `draft`.
- No Candidate Fact import, approval, comparison or database action is performed.

## Evidence rules

1. Add only facts you personally verify.
2. Give every fact a stable `fact_key`, evidence class, statement, capability tags,
   limitations, provenance and optional validity dates.
3. Keep portfolio implementation, training and professional employment distinct.
4. Never treat preferences, target directions or planned capabilities as capability evidence.
5. Employer tags are prompts only and are not candidate truth unless you explicitly enter a
   corresponding private fact.

## Plan-only validation after authoring

After a guided save, validate the draft without Apply:

```bash
.venv/bin/python -m scripts.import_private_candidate_fact_profile \\
  --input private_candidate_facts/{PROFILE_FILENAME} \\
  --applied-by <operator-name>
```

Then run the pair-integrity validator:

```bash
.venv/bin/python -m scripts.run_private_candidate_fact_authoring_integrity
```

Approval and Apply remain separate explicit actions.

## Prohibited shortcuts

- Do not copy facts automatically from chat memory, a CV, uploaded files, project plans or
  target-profile prose.
- Do not convert an employer requirement into a candidate claim.
- Do not mark a fact approved without operator review and valid provenance.
- Do not use the workbook as pipeline input.
- Do not commit any file from this directory.
"""


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_candidate_fact_authoring_pack(
    *,
    output_dir: Path,
    profile_version: str,
    overwrite_token: str | None = None,
) -> CandidateFactAuthoringPack:
    normalized_version = _normalize_profile_version(profile_version)
    profile_path = output_dir / PROFILE_FILENAME
    workbook_path = output_dir / WORKBOOK_FILENAME
    readme_path = output_dir / README_FILENAME
    targets = (profile_path, workbook_path, readme_path)
    existing = tuple(path for path in targets if path.exists())

    if existing and overwrite_token != OVERWRITE_TOKEN:
        names = ", ".join(path.name for path in existing)
        raise FileExistsError(
            "private authoring pack already exists; refusing overwrite without exact "
            f"token {OVERWRITE_TOKEN}: {names}"
        )
    if overwrite_token is not None and overwrite_token != OVERWRITE_TOKEN:
        raise ValueError("invalid private authoring pack overwrite token")

    output_dir.mkdir(parents=True, exist_ok=True)
    profile_payload = build_empty_draft_profile(profile_version=normalized_version)
    workbook_payload = build_eon_authoring_workbook(profile_version=normalized_version)
    readme = build_private_readme(profile_version=normalized_version)

    _write_json(profile_path, profile_payload)
    _write_json(workbook_path, workbook_payload)
    readme_path.write_text(readme, encoding="utf-8")

    return CandidateFactAuthoringPack(
        output_dir=output_dir,
        profile_path=profile_path,
        workbook_path=workbook_path,
        readme_path=readme_path,
        statement_count=len(workbook_payload["requirements"]),
        unique_tag_count=workbook_payload["source_binding"]["unique_tag_count"],
        profile_version=normalized_version,
    )
