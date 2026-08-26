"""Generic deterministic repeated-record navigation induction.

This module performs no network I/O and grants no source, host, job, or Product
authority. It inspects already-fetched HTML from a caller-confirmed career/listing
context and nominates only navigation URLs that are literally present inside a
repeated structural record family.

The contract is deliberately structural rather than company/provider-specific:

* records are grouped by stable HTML tag/class/data-test/role signatures;
* navigation must vary across at least three sibling-like records;
* static links repeated across the whole group are removed;
* records inside navigation/header/footer chrome are ignored;
* a group must carry job-like structure either in its wrapper signature or in the
  observed navigation shapes;
* returned URLs remain diagnostic candidates only and require the existing concrete
  job proof before downstream use.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
import math
import re
from urllib.parse import parse_qsl, urljoin, urlparse


_CONTAINER_TAGS = frozenset({"article", "li", "tr", "section", "div"})
_CHROME_TAGS = frozenset({"nav", "header", "footer"})
_JOB_MARKERS = (
    "job",
    "jobs",
    "career",
    "karriere",
    "stellen",
    "vacanc",
    "position",
    "requisition",
    "opening",
    "role",
)
_BLOCKED_PATH_MARKERS = (
    "/apply",
    "/application",
    "/login",
    "/signin",
    "/register",
    "/privacy",
    "/datenschutz",
    "/contact",
    "/kontakt",
    "/cookie",
    "/share",
)
_STABLE_ATTR_KEYS = ("data-testid", "data-test", "role", "itemprop")
_DYNAMIC_TOKEN = re.compile(r"(?:[0-9a-f]{8,}|\d{5,})", flags=re.IGNORECASE)
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class StructuralRecordGroup:
    signature: str
    record_count: int
    navigation_record_count: int
    distinct_navigation_count: int
    coverage: float
    navigation_urls: tuple[str, ...]
    host_authority: bool = False
    product_authority: bool = False

    def __post_init__(self) -> None:
        if self.host_authority or self.product_authority:
            raise ValueError("structural record induction may not grant authority")


@dataclass
class _Frame:
    tag: str
    signature: str | None
    inside_chrome: bool
    text_parts: list[str] = field(default_factory=list)
    hrefs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Record:
    signature: str
    text: str
    hrefs: tuple[str, ...]


def _compact_text(value: str) -> str:
    return _SPACE.sub(" ", unescape(value or "")).strip()


def _stable_class_tokens(value: str) -> tuple[str, ...]:
    result: list[str] = []
    for raw in str(value or "").split():
        token = raw.casefold().strip()
        if len(token) < 2 or len(token) > 64 or _DYNAMIC_TOKEN.search(token):
            continue
        result.append(token)
    return tuple(sorted(set(result))[:8])


def _record_signature(tag: str, attrs: dict[str, str]) -> str | None:
    normalized_tag = tag.casefold()
    if normalized_tag not in _CONTAINER_TAGS:
        return None

    parts = [normalized_tag]
    classes = _stable_class_tokens(attrs.get("class", ""))
    if classes:
        parts.append("class=" + ".".join(classes))
    for key in _STABLE_ATTR_KEYS:
        value = _compact_text(attrs.get(key, "")).casefold()
        if value and not _DYNAMIC_TOKEN.search(value):
            parts.append(f"{key}={value[:80]}")

    if normalized_tag in {"div", "section"} and len(parts) == 1:
        return None
    return "|".join(parts)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().strip(".")


def _safe_observed_href(
    *,
    page_url: str,
    raw_href: str,
    allowed_hosts: set[str],
) -> str | None:
    target = urljoin(page_url, unescape(str(raw_href or "")).strip())
    parsed = urlparse(target)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    host = parsed.hostname.casefold().strip(".")
    if host not in allowed_hosts:
        return None
    path = parsed.path or "/"
    lowered = path.casefold()
    if any(marker in lowered for marker in _BLOCKED_PATH_MARKERS):
        return None
    if parsed.fragment:
        parsed = parsed._replace(fragment="")
    return parsed.geturl()


def _jobish(value: str) -> bool:
    text = str(value or "").casefold().replace("-", " ").replace("_", " ")
    return any(marker in text for marker in _JOB_MARKERS)


def _jobish_navigation(url: str) -> bool:
    parsed = urlparse(url)
    if _jobish(parsed.path):
        return True
    query_keys = {key.casefold() for key, _value in parse_qsl(parsed.query, keep_blank_values=True)}
    return bool(
        query_keys.intersection(
            {
                "job",
                "jobid",
                "job_id",
                "vacancy",
                "vacancyid",
                "position",
                "positionid",
                "requisition",
                "requisitionid",
            }
        )
    )


def _choose_record_navigation(hrefs: tuple[str, ...], static_targets: set[str]) -> str | None:
    remaining = tuple(dict.fromkeys(href for href in hrefs if href not in static_targets))
    if len(remaining) == 1:
        return remaining[0]
    jobish = tuple(href for href in remaining if _jobish_navigation(href))
    if len(jobish) == 1:
        return jobish[0]
    return None


class _RepeatedRecordParser(HTMLParser):
    def __init__(self, *, page_url: str, allowed_hosts: set[str], max_nodes: int) -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.allowed_hosts = allowed_hosts
        self.max_nodes = max_nodes
        self.nodes_seen = 0
        self.stack: list[_Frame] = []
        self.records: list[_Record] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.casefold()
        if normalized_tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth > 0 or self.nodes_seen >= self.max_nodes:
            return
        self.nodes_seen += 1

        attrs_dict = {
            str(key).casefold(): str(value)
            for key, value in attrs
            if key and value is not None
        }
        inside_chrome = normalized_tag in _CHROME_TAGS or any(
            frame.inside_chrome for frame in self.stack
        )
        frame = _Frame(
            tag=normalized_tag,
            signature=_record_signature(normalized_tag, attrs_dict),
            inside_chrome=inside_chrome,
        )
        self.stack.append(frame)

        if normalized_tag == "a" and not inside_chrome:
            href = attrs_dict.get("href")
            if href:
                target = _safe_observed_href(
                    page_url=self.page_url,
                    raw_href=href,
                    allowed_hosts=self.allowed_hosts,
                )
                if target:
                    for open_frame in self.stack[:-1]:
                        if len(open_frame.hrefs) < 32:
                            open_frame.hrefs.append(target)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.casefold()
        if normalized_tag in {"script", "style", "noscript", "svg"} and self._ignored_depth > 0:
            self._ignored_depth -= 1
            return
        if self._ignored_depth > 0 or not self.stack:
            return

        match_index: int | None = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag == normalized_tag:
                match_index = index
                break
        if match_index is None:
            return

        closing = self.stack[match_index:]
        del self.stack[match_index:]
        for frame in reversed(closing):
            if frame.signature is None or frame.inside_chrome:
                continue
            text = _compact_text(" ".join(frame.text_parts))
            if len(text) < 20 or len(text) > 5000 or not frame.hrefs:
                continue
            self.records.append(
                _Record(
                    signature=frame.signature,
                    text=text,
                    hrefs=tuple(dict.fromkeys(frame.hrefs)),
                )
            )

    def handle_data(self, data: str) -> None:
        if self._ignored_depth > 0:
            return
        value = _compact_text(data)
        if not value:
            return
        for frame in self.stack:
            if len(frame.text_parts) < 256:
                frame.text_parts.append(value[:500])


def induce_structural_record_navigation(
    *,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
    career_context_confirmed: bool,
    min_records: int = 3,
    limit_groups: int = 8,
    max_nodes: int = 50_000,
) -> tuple[StructuralRecordGroup, ...]:
    """Induce repeated-record navigation without creating job/source authority.

    ``career_context_confirmed`` is intentionally caller-owned. This module does
    not decide that an arbitrary page is a careers page. When false it returns no
    candidates. Only exact observed HTTPS links on already-allowed hosts are ever
    returned.
    """

    if not career_context_confirmed or min_records < 3 or limit_groups < 1:
        return ()
    normalized_hosts = {
        str(item).casefold().strip(".") for item in allowed_hosts if str(item).strip()
    }
    if _host(page_url) not in normalized_hosts:
        return ()

    parser = _RepeatedRecordParser(
        page_url=page_url,
        allowed_hosts=normalized_hosts,
        max_nodes=max_nodes,
    )
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        return ()

    grouped: dict[str, list[_Record]] = defaultdict(list)
    for record in parser.records:
        grouped[record.signature].append(record)

    candidates: list[StructuralRecordGroup] = []
    for signature, records in grouped.items():
        if len(records) < min_records:
            continue

        href_record_frequency: Counter[str] = Counter()
        for record in records:
            href_record_frequency.update(set(record.hrefs))
        static_threshold = max(min_records, math.ceil(len(records) * 0.8))
        static_targets = {
            href for href, frequency in href_record_frequency.items() if frequency >= static_threshold
        }

        chosen: list[str] = []
        chosen_record_count = 0
        for record in records:
            target = _choose_record_navigation(record.hrefs, static_targets)
            if target is None:
                continue
            chosen_record_count += 1
            chosen.append(target)

        distinct = tuple(dict.fromkeys(chosen))
        if chosen_record_count < min_records or len(distinct) < min_records:
            continue
        coverage = chosen_record_count / len(records)
        if coverage < 0.6:
            continue

        signature_jobish = _jobish(signature)
        jobish_target_count = sum(1 for target in distinct if _jobish_navigation(target))
        if not signature_jobish and jobish_target_count < min_records:
            continue

        text_variants = {_compact_text(record.text)[:160].casefold() for record in records}
        if len(text_variants) < min_records:
            continue

        candidates.append(
            StructuralRecordGroup(
                signature=signature,
                record_count=len(records),
                navigation_record_count=chosen_record_count,
                distinct_navigation_count=len(distinct),
                coverage=round(coverage, 4),
                navigation_urls=distinct[:32],
            )
        )

    candidates.sort(
        key=lambda item: (
            item.navigation_record_count,
            item.distinct_navigation_count,
            item.coverage,
        ),
        reverse=True,
    )

    seen_urls: set[str] = set()
    result: list[StructuralRecordGroup] = []
    for group in candidates:
        novel_urls = tuple(url for url in group.navigation_urls if url not in seen_urls)
        if len(novel_urls) < min_records:
            continue
        seen_urls.update(novel_urls)
        result.append(
            StructuralRecordGroup(
                signature=group.signature,
                record_count=group.record_count,
                navigation_record_count=group.navigation_record_count,
                distinct_navigation_count=len(novel_urls),
                coverage=group.coverage,
                navigation_urls=novel_urls,
            )
        )
        if len(result) >= limit_groups:
            break
    return tuple(result)


__all__ = ["StructuralRecordGroup", "induce_structural_record_navigation"]
