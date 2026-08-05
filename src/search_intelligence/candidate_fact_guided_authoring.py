from __future__ import annotations

from collections.abc import Callable, Mapping
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Final

from src.search_intelligence.candidate_fact_authoring_integrity import (
    DECISION_EVIDENCE_AVAILABLE,
    DECISION_NEEDS_FOLLOWUP,
    DECISION_NOT_APPLICABLE,
    DECISION_NO_EVIDENCE,
    DECISION_UNREVIEWED,
    FINAL_DECISIONS,
    CandidateFactAuthoringIntegrity,
    validate_candidate_fact_authoring_integrity,
)
from src.search_intelligence.candidate_fact_profile import (
    CandidateFactProfile,
    parse_candidate_fact_profile,
)


GUIDED_AUTHORING_KEY: Final = "CANDIDATE-FACT-GUIDED-AUTHORING-001"
SAVE_CONFIRMATION: Final = "SPEICHERN"

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]
NowFn = Callable[[], datetime]

_DECISION_MENU: Final = {
    "1": DECISION_EVIDENCE_AVAILABLE,
    "2": DECISION_NO_EVIDENCE,
    "3": DECISION_NOT_APPLICABLE,
    "4": DECISION_NEEDS_FOLLOWUP,
    "5": DECISION_UNREVIEWED,
}

_EVIDENCE_CLASSES: Final = (
    "professional_employment",
    "formal_education",
    "portfolio_implementation",
    "training_certification",
    "operator_preference",
    "target_direction",
    "planned_capability",
)

_ALLOWED_CATEGORIES: Final = {
    "professional_employment": ("employment", "skill", "project"),
    "formal_education": ("education", "skill"),
    "portfolio_implementation": ("project", "skill"),
    "training_certification": ("certification", "education", "skill"),
    "operator_preference": ("preference", "boundary"),
    "target_direction": ("target_direction",),
    "planned_capability": ("target_direction", "project", "skill"),
}

_PROVENANCE_TYPES: Final = (
    "operator_assertion",
    "canonical_cv",
    "employment_record",
    "education_record",
    "certificate",
    "repository",
)


class _QuitWithoutSave(Exception):
    pass


@dataclass(frozen=True)
class GuidedAuthoringSessionResult:
    guided_authoring_key: str
    profile_payload: dict[str, Any]
    workbook_payload: dict[str, Any]
    integrity: CandidateFactAuthoringIntegrity
    changed: bool
    save_confirmed: bool
    quit_without_save: bool

    def redacted_summary(self) -> dict[str, Any]:
        return {
            "guided_authoring_key": self.guided_authoring_key,
            "profile_version": self.integrity.profile_version,
            "profile_status": self.integrity.profile_status,
            "profile_fact_count": self.integrity.profile_fact_count,
            "requirement_count": self.integrity.requirement_count,
            "unique_employer_tag_count": self.integrity.unique_employer_tag_count,
            "decision_counts": dict(self.integrity.decision_counts),
            "distinct_referenced_fact_count": (
                self.integrity.distinct_referenced_fact_count
            ),
            "authoring_complete": self.integrity.authoring_complete,
            "blockers": list(self.integrity.blockers),
            "changed": self.changed,
            "save_confirmed": self.save_confirmed,
            "quit_without_save": self.quit_without_save,
            "personal_statements_emitted_in_summary": False,
            "provenance_references_emitted_in_summary": False,
            "capability_tag_values_emitted_in_summary": False,
            "database_reads": 0,
            "database_writes": 0,
            "candidate_fact_import_performed": False,
            "candidate_fact_approval_performed": False,
            "semantic_requirement_comparison_created": False,
            "capability_fit_decision_created": False,
        }


@dataclass(frozen=True)
class SavedAuthoringState:
    backup_dir: Path
    integrity: CandidateFactAuthoringIntegrity


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _pretty_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _read_payload(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{label} does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def load_private_authoring_payloads(
    *,
    profile_path: Path,
    workbook_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], CandidateFactAuthoringIntegrity]:
    profile_payload = _read_payload(profile_path, "private Candidate Fact profile")
    workbook_payload = _read_payload(workbook_path, "private E.ON authoring workbook")
    integrity = validate_candidate_fact_authoring_integrity(
        profile_json=_canonical_json(profile_payload),
        workbook_json=_canonical_json(workbook_payload),
    )
    return profile_payload, workbook_payload, integrity


def _ask(input_fn: InputFn, prompt: str) -> str:
    try:
        value = input_fn(prompt)
    except (EOFError, KeyboardInterrupt) as exc:
        raise _QuitWithoutSave from exc
    if value.strip().casefold() == "q":
        raise _QuitWithoutSave
    return value.strip()


def _choose(
    *,
    input_fn: InputFn,
    output_fn: OutputFn,
    title: str,
    options: tuple[str, ...],
) -> str:
    while True:
        output_fn(title)
        for index, option in enumerate(options, start=1):
            output_fn(f"  [{index}] {option}")
        raw = _ask(input_fn, "Auswahl (q = ohne Speichern beenden): ")
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(options):
                return options[index - 1]
        output_fn("Ungültige Auswahl. Bitte eine angebotene Nummer eingeben.")


def _required_text(input_fn: InputFn, output_fn: OutputFn, prompt: str) -> str:
    while True:
        value = _ask(input_fn, prompt)
        if value:
            return value
        output_fn("Die Eingabe darf nicht leer sein.")


def _csv_values(raw: str) -> list[str]:
    if not raw.strip():
        return []
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if len(values) != len(set(values)):
        raise ValueError("Doppelte Werte sind nicht zulässig.")
    return values


def _optional_note(
    *,
    input_fn: InputFn,
    current: str,
) -> str:
    value = _ask(
        input_fn,
        "Private Notiz (leer = unverändert, '-' = löschen): ",
    )
    if value == "-":
        return ""
    return value if value else current


def _fact_keys(profile_payload: Mapping[str, Any]) -> tuple[str, ...]:
    facts = profile_payload.get("facts")
    if not isinstance(facts, list):
        raise ValueError("private Candidate Fact profile facts must be an array")
    keys: list[str] = []
    for fact in facts:
        if not isinstance(fact, Mapping) or not isinstance(fact.get("fact_key"), str):
            raise ValueError("private Candidate Fact profile contains an invalid fact")
        keys.append(fact["fact_key"])
    return tuple(sorted(keys))


def _select_existing_fact_keys(
    *,
    profile_payload: Mapping[str, Any],
    input_fn: InputFn,
    output_fn: OutputFn,
) -> list[str]:
    available = _fact_keys(profile_payload)
    if not available:
        raise ValueError("Es existiert noch kein Candidate Fact zum Referenzieren.")
    output_fn("Vorhandene Candidate-Fact-Keys:")
    for key in available:
        output_fn(f"  - {key}")
    while True:
        raw = _required_text(
            input_fn,
            output_fn,
            "Fact-Keys kommagetrennt eingeben: ",
        )
        try:
            selected = _csv_values(raw)
        except ValueError as exc:
            output_fn(str(exc))
            continue
        unknown = [key for key in selected if key not in available]
        if unknown:
            output_fn("Mindestens ein eingegebener Fact-Key existiert nicht.")
            continue
        return selected


def _prompt_provenance(
    *,
    evidence_class: str,
    input_fn: InputFn,
    output_fn: OutputFn,
    now_fn: NowFn,
) -> list[dict[str, str]]:
    provenance: list[dict[str, str]] = []
    while True:
        source_type = _choose(
            input_fn=input_fn,
            output_fn=output_fn,
            title="Provenienztyp ausdrücklich auswählen:",
            options=_PROVENANCE_TYPES,
        )
        reference = _required_text(
            input_fn,
            output_fn,
            "Private Provenienzreferenz: ",
        )
        observed_raw = _ask(
            input_fn,
            "Beobachtet am (ISO-8601 mit Zeitzone; leer = jetzt): ",
        )
        observed_at = observed_raw or now_fn().astimezone(timezone.utc).isoformat()
        provenance.append(
            {
                "source_type": source_type,
                "reference": reference,
                "observed_at": observed_at,
            }
        )
        more = _ask(input_fn, "Weitere Provenienz hinzufügen? [j/N]: ")
        if more.casefold() not in {"j", "ja", "y", "yes"}:
            break

    if evidence_class == "portfolio_implementation" and not any(
        item["source_type"] == "repository" for item in provenance
    ):
        output_fn("Portfolio-Evidenz benötigt mindestens eine Repository-Provenienz.")
    if evidence_class == "professional_employment" and not any(
        item["source_type"]
        in {"operator_assertion", "canonical_cv", "employment_record"}
        for item in provenance
    ):
        output_fn(
            "Professionelle Evidenz benötigt Operator-, CV- oder Beschäftigungsprovenienz."
        )
    return provenance


def _prompt_new_fact(
    *,
    profile_payload: dict[str, Any],
    employer_tags: tuple[str, ...],
    input_fn: InputFn,
    output_fn: OutputFn,
    now_fn: NowFn,
) -> str:
    while True:
        output_fn("")
        output_fn("Neuen privaten Candidate Fact als 'proposed' anlegen.")
        output_fn("Die E.ON-Tags sind nur Prüfprompts und werden nicht übernommen:")
        for tag in employer_tags:
            output_fn(f"  - {tag}")

        fact_key = _required_text(input_fn, output_fn, "Eindeutiger fact_key: ")
        evidence_class = _choose(
            input_fn=input_fn,
            output_fn=output_fn,
            title="Evidenzklasse auswählen:",
            options=_EVIDENCE_CLASSES,
        )
        category = _choose(
            input_fn=input_fn,
            output_fn=output_fn,
            title="Passende Kategorie auswählen:",
            options=_ALLOWED_CATEGORIES[evidence_class],
        )
        statement = _required_text(
            input_fn,
            output_fn,
            "Von dir bestätigte Tatsachenaussage: ",
        )

        while True:
            try:
                capability_tags = _csv_values(
                    _ask(
                        input_fn,
                        "Capability-Tags manuell, kommagetrennt (leer erlaubt): ",
                    )
                )
                limitations = _csv_values(
                    _ask(
                        input_fn,
                        "Einschränkungen manuell, kommagetrennt (leer erlaubt): ",
                    )
                )
                break
            except ValueError as exc:
                output_fn(str(exc))

        provenance = _prompt_provenance(
            evidence_class=evidence_class,
            input_fn=input_fn,
            output_fn=output_fn,
            now_fn=now_fn,
        )
        valid_from = _ask(input_fn, "Gültig ab (YYYY-MM-DD; leer = offen): ") or None
        valid_until = _ask(input_fn, "Gültig bis (YYYY-MM-DD; leer = offen): ") or None

        candidate = {
            "fact_key": fact_key,
            "category": category,
            "evidence_class": evidence_class,
            "approval_status": "proposed",
            "statement": statement,
            "capability_tags": capability_tags,
            "limitations": limitations,
            "provenance": provenance,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "approved_by": None,
            "approved_at": None,
        }

        candidate_profile = copy.deepcopy(profile_payload)
        facts = candidate_profile.get("facts")
        if not isinstance(facts, list):
            raise ValueError("private Candidate Fact profile facts must be an array")
        facts.append(candidate)

        try:
            parsed = parse_candidate_fact_profile(candidate_profile)
        except ValueError as exc:
            output_fn(f"Der Fakt ist noch nicht schema-gültig: {exc}")
            retry = _ask(input_fn, "Fakt erneut eingeben? [J/n]: ")
            if retry.casefold() in {"n", "nein", "no"}:
                raise _QuitWithoutSave
            continue

        confirm = _ask(input_fn, "Schema-gültigen Fakt übernehmen? [JA/nein]: ")
        if confirm.casefold() != "ja":
            retry = _ask(input_fn, "Fakt erneut eingeben? [J/n]: ")
            if retry.casefold() in {"n", "nein", "no"}:
                raise _QuitWithoutSave
            continue

        profile_payload.clear()
        profile_payload.update(parsed.canonical_payload())
        output_fn("Candidate Fact wurde lokal im Arbeitsspeicher validiert.")
        return fact_key


def _handle_evidence_available(
    *,
    profile_payload: dict[str, Any],
    employer_tags: tuple[str, ...],
    input_fn: InputFn,
    output_fn: OutputFn,
    now_fn: NowFn,
) -> list[str]:
    options = ("Vorhandenen Candidate Fact referenzieren", "Neuen Candidate Fact anlegen")
    while True:
        action = _choose(
            input_fn=input_fn,
            output_fn=output_fn,
            title="Wie soll die Evidenz erfasst werden?",
            options=options,
        )
        try:
            if action == options[0]:
                return _select_existing_fact_keys(
                    profile_payload=profile_payload,
                    input_fn=input_fn,
                    output_fn=output_fn,
                )
            return [
                _prompt_new_fact(
                    profile_payload=profile_payload,
                    employer_tags=employer_tags,
                    input_fn=input_fn,
                    output_fn=output_fn,
                    now_fn=now_fn,
                )
            ]
        except ValueError as exc:
            output_fn(str(exc))


def _update_truth_state(workbook_payload: dict[str, Any]) -> None:
    requirements = workbook_payload.get("requirements")
    if not isinstance(requirements, list):
        raise ValueError("private E.ON authoring workbook requirements must be an array")
    decisions: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, Mapping):
            raise ValueError("private E.ON authoring workbook contains invalid requirement")
        review = requirement.get("operator_review")
        if not isinstance(review, Mapping):
            raise ValueError("private E.ON authoring workbook contains invalid review")
        decision = review.get("evidence_decision")
        if not isinstance(decision, str):
            raise ValueError("private E.ON authoring workbook contains invalid decision")
        decisions.append(decision)

    if decisions and all(decision in FINAL_DECISIONS for decision in decisions):
        workbook_payload["candidate_truth_state"] = "operator_reviewed"
    elif any(decision != DECISION_UNREVIEWED for decision in decisions):
        workbook_payload["candidate_truth_state"] = "in_progress"
    else:
        workbook_payload["candidate_truth_state"] = "not_authored"


def _emit_redacted_progress(
    *,
    integrity: CandidateFactAuthoringIntegrity,
    output_fn: OutputFn,
) -> None:
    reviewed = integrity.requirement_count - integrity.decision_counts.get(
        DECISION_UNREVIEWED, 0
    )
    output_fn("")
    output_fn("Redaktierte Authoring-Zusammenfassung")
    output_fn(f"  geprüft: {reviewed}/{integrity.requirement_count}")
    output_fn(f"  private Fakten: {integrity.profile_fact_count}")
    output_fn(
        "  Entscheidungen: "
        + ", ".join(
            f"{key}={value}" for key, value in integrity.decision_counts.items()
        )
    )
    output_fn(f"  authoring_complete: {str(integrity.authoring_complete).lower()}")
    output_fn(
        "  blockers: "
        + (", ".join(integrity.blockers) if integrity.blockers else "none")
    )


def run_guided_authoring_session(
    *,
    profile_payload: Mapping[str, Any],
    workbook_payload: Mapping[str, Any],
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    now_fn: NowFn = lambda: datetime.now(timezone.utc),
) -> GuidedAuthoringSessionResult:
    original_profile = copy.deepcopy(dict(profile_payload))
    original_workbook = copy.deepcopy(dict(workbook_payload))
    original_integrity = validate_candidate_fact_authoring_integrity(
        profile_json=_canonical_json(original_profile),
        workbook_json=_canonical_json(original_workbook),
    )

    working_profile = copy.deepcopy(original_profile)
    working_workbook = copy.deepcopy(original_workbook)

    try:
        requirements = working_workbook.get("requirements")
        if not isinstance(requirements, list):
            raise ValueError("private E.ON authoring workbook requirements must be an array")

        output_fn("Geführtes privates Candidate-Fact-Authoring")
        output_fn("q beendet jederzeit ohne Speichern.")
        output_fn("Es werden keine persönlichen Fakten automatisch erzeugt.")

        for index, requirement in enumerate(requirements, start=1):
            if not isinstance(requirement, dict):
                raise ValueError("private E.ON authoring workbook contains invalid requirement")
            review = requirement.get("operator_review")
            if not isinstance(review, dict):
                raise ValueError("private E.ON authoring workbook contains invalid review")
            employer_tags_raw = requirement.get("canonical_employer_tags")
            if not isinstance(employer_tags_raw, list) or not all(
                isinstance(item, str) for item in employer_tags_raw
            ):
                raise ValueError("private E.ON authoring workbook contains invalid tags")
            employer_tags = tuple(employer_tags_raw)

            output_fn("")
            output_fn("=" * 78)
            output_fn(f"Anforderung {index}/{len(requirements)}")
            output_fn(str(requirement.get("employer_statement", "")))
            output_fn("E.ON-Tags – nur als Prüfprompts, nicht als Kandidatenwahrheit:")
            for tag in employer_tags:
                output_fn(f"  - {tag}")
            output_fn(
                "Aktuelle Entscheidung: "
                f"{review.get('evidence_decision', DECISION_UNREVIEWED)}"
            )
            output_fn("  [1] Evidenz vorhanden")
            output_fn("  [2] Keine Evidenz")
            output_fn("  [3] Nicht anwendbar")
            output_fn("  [4] Klärung nötig")
            output_fn("  [5] Ungeprüft lassen")

            while True:
                choice = _ask(input_fn, "Entscheidung (1-5, q = Ende): ")
                decision = _DECISION_MENU.get(choice)
                if decision is not None:
                    break
                output_fn("Ungültige Auswahl. Bitte 1 bis 5 eingeben.")

            fact_keys: list[str] = []
            if decision == DECISION_EVIDENCE_AVAILABLE:
                fact_keys = _handle_evidence_available(
                    profile_payload=working_profile,
                    employer_tags=employer_tags,
                    input_fn=input_fn,
                    output_fn=output_fn,
                    now_fn=now_fn,
                )

            current_note = review.get("private_notes")
            if not isinstance(current_note, str):
                raise ValueError("private E.ON authoring workbook contains invalid notes")
            review["evidence_decision"] = decision
            review["candidate_fact_keys"] = fact_keys
            review["private_notes"] = _optional_note(
                input_fn=input_fn,
                current=current_note,
            )

            _update_truth_state(working_workbook)
            partial_integrity = validate_candidate_fact_authoring_integrity(
                profile_json=_canonical_json(working_profile),
                workbook_json=_canonical_json(working_workbook),
            )
            _emit_redacted_progress(
                integrity=partial_integrity,
                output_fn=output_fn,
            )

        _update_truth_state(working_workbook)
        parsed_profile: CandidateFactProfile = parse_candidate_fact_profile(
            working_profile
        )
        working_profile = parsed_profile.canonical_payload()
        final_integrity = validate_candidate_fact_authoring_integrity(
            profile_json=_canonical_json(working_profile),
            workbook_json=_canonical_json(working_workbook),
        )
        _emit_redacted_progress(integrity=final_integrity, output_fn=output_fn)

        confirmation = _ask(
            input_fn,
            f"Zum Schreiben beider privaten Dateien exakt {SAVE_CONFIRMATION} eingeben: ",
        )
        save_confirmed = confirmation == SAVE_CONFIRMATION
        if not save_confirmed:
            output_fn("Keine Speicherung bestätigt. Beide Dateien bleiben unverändert.")

        changed = (
            _canonical_json(working_profile) != _canonical_json(original_profile)
            or _canonical_json(working_workbook) != _canonical_json(original_workbook)
        )
        return GuidedAuthoringSessionResult(
            guided_authoring_key=GUIDED_AUTHORING_KEY,
            profile_payload=working_profile,
            workbook_payload=working_workbook,
            integrity=final_integrity,
            changed=changed,
            save_confirmed=save_confirmed,
            quit_without_save=False,
        )
    except _QuitWithoutSave:
        output_fn("Authoring beendet. Beide Dateien bleiben unverändert.")
        return GuidedAuthoringSessionResult(
            guided_authoring_key=GUIDED_AUTHORING_KEY,
            profile_payload=original_profile,
            workbook_payload=original_workbook,
            integrity=original_integrity,
            changed=False,
            save_confirmed=False,
            quit_without_save=True,
        )


def _atomic_replace(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def save_private_authoring_payloads(
    *,
    profile_path: Path,
    workbook_path: Path,
    profile_payload: Mapping[str, Any],
    workbook_payload: Mapping[str, Any],
    now_fn: NowFn = lambda: datetime.now(timezone.utc),
) -> SavedAuthoringState:
    profile_content = _pretty_json_bytes(profile_payload)
    workbook_content = _pretty_json_bytes(workbook_payload)
    integrity = validate_candidate_fact_authoring_integrity(
        profile_json=profile_content.decode("utf-8"),
        workbook_json=workbook_content.decode("utf-8"),
    )

    original_profile = profile_path.read_bytes()
    original_workbook = workbook_path.read_bytes()
    stamp = now_fn().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir = profile_path.parent / "backups" / stamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    (backup_dir / profile_path.name).write_bytes(original_profile)
    (backup_dir / workbook_path.name).write_bytes(original_workbook)

    try:
        _atomic_replace(profile_path, profile_content)
        _atomic_replace(workbook_path, workbook_content)
    except Exception:
        _atomic_replace(profile_path, original_profile)
        _atomic_replace(workbook_path, original_workbook)
        raise

    return SavedAuthoringState(backup_dir=backup_dir, integrity=integrity)
