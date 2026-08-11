from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Protocol, Sequence, TypeVar
from urllib.parse import unquote, urlsplit

from src.job_lifecycle_health import normalize_text


DETAIL_CANDIDATE_SELECTION_VERSION = "DETAIL-BUDGET-001"

_GENDER_AND_FORMAT_NOISE = {
    "m",
    "w",
    "d",
    "f",
    "x",
    "gn",
    "mwd",
    "wmd",
    "dwm",
}
_URL_ROUTE_NOISE = {
    "de",
    "en",
    "job",
    "jobs",
    "karriere",
    "career",
    "careers",
    "stellenangebote",
    "details",
    "detail",
    "html",
}


class DetailLinkLike(Protocol):
    url: str
    text: str


TDetailLink = TypeVar("TDetailLink", bound=DetailLinkLike)


@dataclass(frozen=True)
class DetailCandidateSelection:
    selected_rank: int
    original_index: int
    url: str
    link_text: str
    relevance_score: int
    exact_core_match: bool
    target_token_count: int
    link_token_overlap: int
    url_token_overlap: int
    link_sequence_score: int
    url_sequence_score: int
    reason: str

    def to_evidence(self) -> dict[str, object]:
        return {
            "selected_rank": self.selected_rank,
            "original_index": self.original_index,
            "url": self.url,
            "link_text": self.link_text,
            "relevance_score": self.relevance_score,
            "exact_core_match": self.exact_core_match,
            "target_token_count": self.target_token_count,
            "link_token_overlap": self.link_token_overlap,
            "url_token_overlap": self.url_token_overlap,
            "link_sequence_score": self.link_sequence_score,
            "url_sequence_score": self.url_sequence_score,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class _ScoredCandidate:
    original_index: int
    candidate: DetailLinkLike
    relevance_score: int
    exact_core_match: bool
    target_token_count: int
    link_token_overlap: int
    url_token_overlap: int
    link_sequence_score: int
    url_sequence_score: int


def _normalized_core(value: str) -> str:
    tokens = [
        token
        for token in normalize_text(value).split()
        if token not in _GENDER_AND_FORMAT_NOISE
    ]
    return " ".join(tokens)


def _target_core(title: str, company_name: str) -> str:
    normalized_title = _normalized_core(title)
    normalized_company = _normalized_core(company_name)
    if normalized_company and normalized_title.startswith(normalized_company + " "):
        normalized_title = normalized_title[len(normalized_company) + 1 :]
    return normalized_title


def _url_core(url: str) -> str:
    parsed = urlsplit(url)
    path = unquote(parsed.path or "")
    tokens: list[str] = []
    for token in _normalized_core(path).split():
        if token in _URL_ROUTE_NOISE:
            continue
        if token.startswith("j") and token[1:].isdigit():
            continue
        if token.isdigit():
            continue
        tokens.append(token)
    return " ".join(tokens)


def _token_overlap(target: str, candidate: str) -> tuple[int, int]:
    target_tokens = tuple(dict.fromkeys(target.split()))
    candidate_tokens = set(candidate.split())
    overlap = sum(token in candidate_tokens for token in target_tokens)
    return len(target_tokens), overlap


def _sequence_score(target: str, candidate: str) -> int:
    if not target or not candidate:
        return 0
    return int(round(SequenceMatcher(None, target, candidate).ratio() * 1000))


def _score_candidate(
    *,
    target_core: str,
    candidate: DetailLinkLike,
    original_index: int,
) -> _ScoredCandidate:
    link_core = _normalized_core(candidate.text)
    url_core = _url_core(candidate.url)
    target_token_count, link_overlap = _token_overlap(target_core, link_core)
    _, url_overlap = _token_overlap(target_core, url_core)
    link_sequence = _sequence_score(target_core, link_core)
    url_sequence = _sequence_score(target_core, url_core)

    exact_core_match = bool(
        target_core
        and link_core
        and (
            target_core == link_core
            or target_core in link_core
            or (
                link_core in target_core
                and link_overlap == target_token_count
            )
        )
    )
    recall_milli = (
        int(round((link_overlap / target_token_count) * 1000))
        if target_token_count
        else 0
    )

    relevance_score = (
        (10_000 if exact_core_match else 0)
        + link_overlap * 500
        + recall_milli * 3
        + link_sequence * 2
        + url_overlap * 150
        + url_sequence // 2
    )
    return _ScoredCandidate(
        original_index=original_index,
        candidate=candidate,
        relevance_score=relevance_score,
        exact_core_match=exact_core_match,
        target_token_count=target_token_count,
        link_token_overlap=link_overlap,
        url_token_overlap=url_overlap,
        link_sequence_score=link_sequence,
        url_sequence_score=url_sequence,
    )


def prioritize_detail_candidates(
    *,
    target_title: str,
    company_name: str,
    candidates: Sequence[TDetailLink],
    limit: int,
) -> tuple[tuple[TDetailLink, ...], tuple[DetailCandidateSelection, ...]]:
    """Spend a fixed detail-page budget on title-relevant employer-origin links.

    This is deliberately only a deterministic budget-ordering heuristic. It does
    not confirm vacancy identity or activity. Existing exact-title and lifecycle
    health gates remain authoritative after the selected pages are fetched.
    Ties preserve original discovery order, so completely uninformative candidate
    sets remain behaviorally stable and bounded.
    """

    if limit <= 0:
        raise ValueError("limit must be positive")

    target_core = _target_core(target_title, company_name)
    scored = [
        _score_candidate(
            target_core=target_core,
            candidate=candidate,
            original_index=index,
        )
        for index, candidate in enumerate(candidates)
    ]
    scored.sort(key=lambda item: (-item.relevance_score, item.original_index))
    selected_scored = scored[:limit]

    selected = tuple(item.candidate for item in selected_scored)
    evidence = tuple(
        DetailCandidateSelection(
            selected_rank=rank,
            original_index=item.original_index,
            url=item.candidate.url,
            link_text=item.candidate.text,
            relevance_score=item.relevance_score,
            exact_core_match=item.exact_core_match,
            target_token_count=item.target_token_count,
            link_token_overlap=item.link_token_overlap,
            url_token_overlap=item.url_token_overlap,
            link_sequence_score=item.link_sequence_score,
            url_sequence_score=item.url_sequence_score,
            reason=(
                "deterministic target-title relevance ordering before fixed "
                "detail-page budget; not vacancy-identity evidence"
            ),
        )
        for rank, item in enumerate(selected_scored, start=1)
    )
    return selected, evidence
