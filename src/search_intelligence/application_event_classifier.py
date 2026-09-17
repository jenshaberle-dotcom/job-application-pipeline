"""Deterministic-first classification for bounded application communication evidence.

This module owns no mailbox access and no application-state authority. It accepts
already-normalized, bounded evidence and emits an evidence candidate only. Model
assistance, if introduced later, is restricted to residual ambiguity outside this
module's authoritative behavior.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


CANDIDATE_CLASSES = (
    "application_acknowledgement",
    "recruiter_contact",
    "interview_invitation",
    "assessment_request",
    "offer_signal",
    "rejection",
    "withdrawal_confirmation",
    "other",
    "ambiguous",
)


@dataclass(frozen=True)
class ClassificationResult:
    candidate_class: str
    confidence: float | None
    reason_code: str
    evidence_span: str | None
    matched_terms: tuple[str, ...]
    deterministic: bool = True
    authority: str = "evidence_only"

    def as_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["matched_terms"] = list(self.matched_terms)
        return payload


_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "rejection": (
        (r"\bleider\s+(?:nicht|keine)\b", "leider nicht"),
        (r"\babsage\b", "Absage"),
        (r"\bnicht\s+berücksichtigen\b", "nicht berücksichtigen"),
        (r"\bnot\s+(?:be\s+)?moving\s+forward\b", "not moving forward"),
        (r"\bregret\s+to\s+inform\b", "regret to inform"),
        (r"\bunsuccessful\b", "unsuccessful"),
    ),
    "offer_signal": (
        (r"\b(?:job|employment)\s+offer\b", "job offer"),
        (r"\bangebot\s+(?:für|zur)\s+(?:die\s+)?(?:stelle|position)\b", "Angebot für die Stelle"),
        (r"\bvertragsangebot\b", "Vertragsangebot"),
        (r"\bwe\s+would\s+like\s+to\s+offer\s+you\b", "we would like to offer you"),
    ),
    "interview_invitation": (
        (r"\b(?:einladung|termin)\s+(?:zu|zum|für)\s+(?:einem\s+)?(?:vorstellungsgespräch|interview)\b", "Einladung zum Interview"),
        (r"\bvorstellungsgespräch\b", "Vorstellungsgespräch"),
        (r"\binterview\s+(?:invitation|appointment|slot)\b", "interview invitation"),
        (r"\binvite\s+you\s+(?:to|for)\s+(?:an?\s+)?interview\b", "invite you to interview"),
    ),
    "assessment_request": (
        (
            r"\bassessment\s+(?:request|invitation|invite|link|test|centre|center)\b",
            "assessment request",
        ),
        (r"\b(?:coding\s+challenge|case\s+study|take[- ]home)\b", "assessment request"),
        (r"\b(?:online[- ]?test|eignungstest|fachtest|arbeitsprobe)\b", "assessment request"),
    ),
    "application_acknowledgement": (
        (r"\b(?:bewerbung|application)\s+(?:ist\s+)?(?:eingegangen|received)\b", "application received"),
        (r"\bvielen\s+dank\s+für\s+(?:ihre|deine)\s+bewerbung\b", "Danke für Bewerbung"),
        (r"\bthank\s+you\s+for\s+(?:your\s+)?application\b", "thank you for your application"),
        (r"\bwe\s+have\s+received\s+your\s+application\b", "we have received your application"),
    ),
    "withdrawal_confirmation": (
        (r"\b(?:rückzug|zurückziehung)\s+(?:ihrer|deiner)\s+bewerbung\b", "Rückzug der Bewerbung"),
        (r"\bwithdrawal\s+of\s+(?:your\s+)?application\b", "withdrawal of application"),
    ),
    "recruiter_contact": (
        (r"\b(?:recruiter|talent\s+acquisition|personalabteilung|recruiting)\b", "recruiter contact"),
        (r"\b(?:kurzes|kurzen)\s+(?:telefonat|gespräch|kennenlernen)\b", "recruiter conversation"),
        (r"\b(?:phone|screening)\s+call\b", "screening call"),
    ),
}

_CLASS_PRIORITY = (
    "rejection",
    "offer_signal",
    "interview_invitation",
    "assessment_request",
    "withdrawal_confirmation",
    "application_acknowledgement",
    "recruiter_contact",
)
_HIGH_IMPACT_CLASSES = frozenset(
    {
        "rejection",
        "offer_signal",
        "interview_invitation",
        "assessment_request",
        "withdrawal_confirmation",
    }
)
_DETERMINISTIC_EVENT_SIGNALS = _HIGH_IMPACT_CLASSES

_APPLICATION_CONTEXT = re.compile(
    r"\b(?:bewerbung|bewerbungsprozess|application|candidate|candidacy|"
    r"stelle|position|job|recruiting|recruitment|talent\s+acquisition|"
    r"vorstellungsgespräch|interview)\b",
    re.I,
)
_OUTBOUND_APPLICATION_SUBJECT = re.compile(
    r"^(?:re:\s*)?(?:bewerbung\s+(?:als|für|auf)|initiativbewerbung\b|"
    r"application\s+(?:for|as)|unsolicited\s+application\b)",
    re.I,
)


def _normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _matches(text: str, rules: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for pattern, label in rules:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            result.append((label, match.group(0)))
    return result


def _has_application_context(text: str) -> bool:
    return bool(_APPLICATION_CONTEXT.search(text))


def _normalized_event_signals(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    result: list[str] = []
    for value in values:
        signal = _normalize(value)
        if signal in _DETERMINISTIC_EVENT_SIGNALS and signal not in result:
            result.append(signal)
    return tuple(result)


def _ambiguous_result(
    class_matches: dict[str, list[tuple[str, str]]],
) -> ClassificationResult:
    terms = tuple(
        label
        for candidate_class in _CLASS_PRIORITY
        for label, _ in class_matches.get(candidate_class, [])
    )
    first_span = next(
        span
        for candidate_class in _CLASS_PRIORITY
        for _, span in class_matches.get(candidate_class, [])
    )
    return ClassificationResult(
        candidate_class="ambiguous",
        confidence=None,
        reason_code="multiple_deterministic_classes",
        evidence_span=first_span[:240],
        matched_terms=terms,
    )


def _deterministic_result(
    candidate_class: str,
    matches: list[tuple[str, str]],
) -> ClassificationResult:
    confidence = 0.97 if candidate_class in {"rejection", "offer_signal"} else 0.95
    return ClassificationResult(
        candidate_class=candidate_class,
        confidence=confidence,
        reason_code=f"deterministic_{candidate_class}",
        evidence_span=matches[0][1][:240],
        matched_terms=tuple(label for label, _ in matches),
    )


def classify_application_evidence(
    *,
    subject: str | None,
    text_excerpt: str | None,
    sender_domain: str | None = None,
    mail_direction: str | None = None,
    counterparty_domain: str | None = None,
    deterministic_event_signals: Iterable[str] | None = None,
) -> ClassificationResult:
    """Classify one bounded communication excerpt without creating state authority."""

    subject_text = _normalize(subject)
    excerpt_text = _normalize(text_excerpt)
    combined = f"{subject_text}\n{excerpt_text}".strip()
    event_signals = _normalized_event_signals(deterministic_event_signals)
    if not combined and not event_signals:
        return ClassificationResult(
            candidate_class="ambiguous",
            confidence=None,
            reason_code="insufficient_bounded_evidence",
            evidence_span=None,
            matched_terms=(),
        )

    direction = _normalize(mail_direction)
    if direction == "outbound" and _OUTBOUND_APPLICATION_SUBJECT.search(subject_text):
        # Keep the schema's existing applied-observation bucket while preserving
        # the materially different evidence reason. This is mailbox evidence only;
        # it does not create application_submissions authority.
        return ClassificationResult(
            candidate_class="application_acknowledgement",
            confidence=0.99,
            reason_code="deterministic_outbound_application_sent",
            evidence_span=subject_text[:240],
            matched_terms=("outbound application sent",),
        )

    class_matches: dict[str, list[tuple[str, str]]] = {}
    has_application_context = _has_application_context(combined)
    for candidate_class in _CLASS_PRIORITY:
        matches = _matches(combined, _RULES[candidate_class]) if combined else []
        if matches:
            # Words such as "Absage" and "assessment" are common outside recruiting.
            # High-impact rejection and assessment evidence therefore require bounded
            # application/recruiting context before they may become lifecycle evidence.
            if candidate_class in {"rejection", "assessment_request"} and not has_application_context:
                matches = []
        if candidate_class in event_signals:
            matches.append(
                (
                    f"bounded event signal: {candidate_class}",
                    f"deterministic_event_signal:{candidate_class}",
                )
            )
        if matches:
            class_matches[candidate_class] = matches

    high_impact_matches = [
        candidate_class
        for candidate_class in _CLASS_PRIORITY
        if candidate_class in _HIGH_IMPACT_CLASSES and candidate_class in class_matches
    ]
    if len(high_impact_matches) > 1:
        return _ambiguous_result(class_matches)
    if len(high_impact_matches) == 1:
        candidate_class = high_impact_matches[0]
        return _deterministic_result(candidate_class, class_matches[candidate_class])

    # Acknowledgement language frequently names the recruiting function as part of
    # the same receipt. That is one clear receipt event, not a lifecycle conflict.
    if "application_acknowledgement" in class_matches:
        return _deterministic_result(
            "application_acknowledgement",
            class_matches["application_acknowledgement"],
        )

    if len(class_matches) > 1:
        return _ambiguous_result(class_matches)

    if len(class_matches) == 1:
        candidate_class = next(iter(class_matches))
        return _deterministic_result(candidate_class, class_matches[candidate_class])

    domain = _normalize(counterparty_domain) or _normalize(sender_domain)
    if domain:
        return ClassificationResult(
            candidate_class="other",
            confidence=0.40,
            reason_code="no_deterministic_event_phrase",
            evidence_span=None,
            matched_terms=(domain,),
        )

    return ClassificationResult(
        candidate_class="ambiguous",
        confidence=None,
        reason_code="no_deterministic_signal",
        evidence_span=None,
        matched_terms=(),
    )
