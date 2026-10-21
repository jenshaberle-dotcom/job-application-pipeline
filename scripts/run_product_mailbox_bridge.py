"""Product evidence policy around the unchanged private, read-only Gmail bridge."""
from __future__ import annotations
import importlib
from pathlib import Path
import re
import sys


def enrich_identity(row: dict) -> dict:
    result = dict(row)
    subject = str(row.get("subject") or "").strip()
    subject = re.sub(r"^(?:(?:re|aw|fw|wg):\s*)+", "", subject, flags=re.I)
    match = re.fullmatch(r"(?:Deine|Ihre) Bewerbung bei (.+?)(?: als (.+))?", subject, re.I)
    if match:
        company, title = match.groups()
        # Explicit subject evidence outranks a pronoun extracted from boilerplate.
        if str(row.get("employer_name") or "").casefold() in {"", "uns", "us", "wir", "we"}:
            result["employer_name"] = company.strip()
            result["employer_evidence_source"] = "application_subject"
        if not row.get("job_title") and title:
            result["job_title"] = title.strip()
    # Extract only an explicit role in the subject, never infer one from the
    # employer, signature, or a generic acknowledgement sentence.
    role = re.fullmatch(
        r"(?:Deine|Ihre) Bewerbung (?:auf|für) (?:die|unsere) (?:Stelle|Position)\s+(.+)",
        subject, re.I,
    )
    if role and not result.get("job_title"):
        title = role.group(1).strip().strip('"„“')
        if 3 <= len(title) <= 240 and not re.match(r"(?:ist|wurde|bei uns)\b", title, re.I):
            result["job_title"] = title
    return result


def install_policy(bridge):
    bridge._GMAIL_SEARCH_SIGNAL_QUERIES = tuple(
        (kind, query[:-1] + ' "müssen wir dir leider absagen" "müssen wir Ihnen leider absagen" "dein Profil nicht ganz unseren Vorstellungen" "Bewerbung nicht weiter in der engeren Auswahl berücksichtigen" "Bewerbung nicht in die engere Auswahl gekommen"}')
        if kind == "rejection" else
        (kind, query[:-1] + ' "zu einem Gespräch einladen"}') if kind == 'interview_invitation' else
        (kind, query[:-1] + ' "ziehe meine Bewerbung zurück" "Rückzug Ihrer Bewerbung"}') if kind == 'withdrawal_confirmation' else (kind, query)
        for kind, query in bridge._GMAIL_SEARCH_SIGNAL_QUERIES
    )
    original = bridge._impl.normalize_gmail_message
    def normalize(*args, **kwargs):
        return enrich_identity(original(*args, **kwargs))
    bridge._impl.normalize_gmail_message = normalize


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--bridge-path":
        raise SystemExit("private_bridge_path_required")
    path = Path(sys.argv[2]).resolve(strict=True)
    if path.name != "f5_gmail_readonly_bridge.py":
        raise SystemExit("unexpected_private_bridge")
    sys.path.insert(0, str(path.parent))
    del sys.argv[1:3]
    bridge = importlib.import_module("f5_gmail_readonly_bridge")
    install_policy(bridge)
    return bridge.main()


if __name__ == "__main__":
    raise SystemExit(main())
