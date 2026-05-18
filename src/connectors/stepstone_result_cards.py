from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


RESULT_CARD_SELECTOR_DESCRIPTION = 'article[data-testid="job-item"]'
TITLE_LINK_TEST_ID = "job-item-title"


@dataclass(frozen=True)
class ResultCardBlock:
    external_job_id: str
    raw_html: str
    start_position: int
    end_position: int


@dataclass(frozen=True)
class ResultCardFields:
    index: int
    external_job_id: str
    title: str | None
    company: str | None
    location: str | None
    detail_url: str | None
    raw_href: str | None
    card_html_bytes: int
    title_id_matches_article_id: bool
    data_at_fields: dict[str, str]
    raw_card_text: str
    publication_hint_text: str | None
    salary_hint_text: str | None
    salary_ui_prompt_text: str | None
    remote_hint_text: str | None
    employment_type_hint_text: str | None


class CardParser(HTMLParser):
    """Extract source-preserving fields from one StepStone result-card block."""

    def __init__(self) -> None:
        super().__init__()

        self.title_href: str | None = None
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

        self.data_at_fields: dict[str, list[str]] = {}

        self._ignored_depth = 0
        self._title_depth: int | None = None
        self._data_at_captures: list[dict[str, object]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized_tag = tag.lower()

        if normalized_tag in {"style", "script"}:
            self._ignored_depth += 1
            return

        if self._ignored_depth > 0:
            return

        if self._title_depth is not None:
            self._title_depth += 1

        for capture in self._data_at_captures:
            capture["depth"] = int(capture["depth"]) + 1

        attrs_dict = normalize_attrs(attrs)

        data_testid = attrs_dict.get("data-testid")
        data_at = attrs_dict.get("data-at")

        if normalized_tag == "a" and data_testid == TITLE_LINK_TEST_ID:
            self.title_href = attrs_dict.get("href")
            self._title_depth = 1
            self.title_parts = []

        if data_at:
            self._data_at_captures.append(
                {
                    "name": data_at,
                    "depth": 1,
                }
            )
            self.data_at_fields.setdefault(data_at, [])

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()

        if normalized_tag in {"style", "script"} and self._ignored_depth > 0:
            self._ignored_depth -= 1
            return

        if self._ignored_depth > 0:
            return

        if self._title_depth is not None:
            self._title_depth -= 1

            if self._title_depth <= 0:
                self._title_depth = None

        remaining_captures: list[dict[str, object]] = []

        for capture in self._data_at_captures:
            capture["depth"] = int(capture["depth"]) - 1

            if int(capture["depth"]) > 0:
                remaining_captures.append(capture)

        self._data_at_captures = remaining_captures

    def handle_data(self, data: str) -> None:
        if self._ignored_depth > 0:
            return

        self.text_parts.append(data)

        if self._title_depth is not None:
            self.title_parts.append(data)

        for capture in self._data_at_captures:
            name = str(capture["name"])
            self.data_at_fields.setdefault(name, []).append(data)

    @property
    def title(self) -> str | None:
        value = compact_text(" ".join(self.title_parts))
        return value or None

    @property
    def raw_text(self) -> str:
        return compact_text(" ".join(self.text_parts))

    @property
    def compact_data_at_fields(self) -> dict[str, str]:
        result: dict[str, str] = {}

        for key, parts in self.data_at_fields.items():
            value = compact_text(" ".join(parts))

            if value:
                result[key] = value

        return result


def normalize_attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {
        key.lower(): value
        for key, value in attrs
        if value is not None
    }


def compact_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_attr_from_tag(tag: str, attr_name: str) -> str | None:
    pattern = re.compile(
        rf"\b{re.escape(attr_name)}\s*=\s*(['\"])(.*?)\1",
        flags=re.IGNORECASE | re.DOTALL,
    )

    match = pattern.search(tag)

    if not match:
        return None

    return html.unescape(match.group(2))


def is_stepstone_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("stepstone.de")


def looks_like_job_detail_url(url: str) -> bool:
    return "stellenangebote" in url and re.search(r"--\d+.*\.html", url) is not None


def extract_stepstone_id_from_url(url: str | None) -> str | None:
    if not url:
        return None

    match = re.search(r"--(\d+)-inline\.html", url)

    if not match:
        return None

    return match.group(1)


def iter_article_blocks(raw_html: str) -> list[ResultCardBlock]:
    blocks: list[ResultCardBlock] = []

    for match in re.finditer(
        r"<article\b[^>]*>",
        raw_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        opening_tag = match.group(0)

        data_testid = extract_attr_from_tag(opening_tag, "data-testid")
        article_id = extract_attr_from_tag(opening_tag, "id")

        if data_testid != "job-item":
            continue

        if not article_id:
            continue

        id_match = re.fullmatch(r"job-item-(\d+)", article_id)

        if not id_match:
            continue

        close_position = raw_html.find("</article>", match.end())

        if close_position < 0:
            continue

        end_position = close_position + len("</article>")

        blocks.append(
            ResultCardBlock(
                external_job_id=id_match.group(1),
                raw_html=raw_html[match.start():end_position],
                start_position=match.start(),
                end_position=end_position,
            )
        )

    return blocks


def find_first_job_detail_href(card_html: str) -> str | None:
    for match in re.finditer(
        r"<a\b[^>]*>",
        card_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        opening_tag = match.group(0)
        href = extract_attr_from_tag(opening_tag, "href")

        if href and looks_like_job_detail_url(href):
            return href

    return None


def find_field_by_exact_keys(
    fields: dict[str, str],
    keys: list[str],
) -> str | None:
    for key in keys:
        value = fields.get(key)

        if value:
            return value

    return None


def find_field_by_name_fragment(
    fields: dict[str, str],
    fragments: list[str],
    excluded_fragments: list[str] | None = None,
) -> str | None:
    excluded_fragments = excluded_fragments or []

    for key, value in fields.items():
        lower_key = key.lower()

        if any(fragment in lower_key for fragment in excluded_fragments):
            continue

        if any(fragment in lower_key for fragment in fragments):
            return value

    return None


def extract_company(fields: dict[str, str]) -> str | None:
    return (
        find_field_by_exact_keys(
            fields,
            [
                "job-item-company-name",
                "company-name",
                "company",
            ],
        )
        or find_field_by_name_fragment(
            fields,
            fragments=["company", "arbeitgeber", "employer"],
            excluded_fragments=["logo"],
        )
    )


def extract_location(fields: dict[str, str]) -> str | None:
    return (
        find_field_by_exact_keys(
            fields,
            [
                "job-item-location",
                "job-location",
                "location",
            ],
        )
        or find_field_by_name_fragment(
            fields,
            fragments=["location", "ort", "standort"],
        )
    )


def extract_publication_hint_text(
    fields: dict[str, str],
    raw_card_text: str,
) -> str | None:
    field_value = find_field_by_name_fragment(
        fields,
        fragments=["date", "posted", "publication", "veröffentlich", "time"],
    )

    if field_value:
        return field_value

    patterns = [
        r"\bHeute\b",
        r"\bGestern\b",
        r"\bGerade eben\b",
        r"\bvor\s+\d+\s+(?:Minuten|Stunden|Tagen|Wochen)\b",
        r"\b\d+\s+(?:Minuten|Stunden|Tage|Wochen)\s+alt\b",
    ]

    return find_first_text_match(raw_card_text, patterns)


def contains_salary_amount(value: str) -> bool:
    return re.search(
        r"\b(?:\d[\d\.\,]*\s*(?:€|EUR)|(?:€|EUR)\s*\d[\d\.\,]*)\b",
        value,
        flags=re.IGNORECASE,
    ) is not None


def extract_salary_hint_text(
    fields: dict[str, str],
    raw_card_text: str,
) -> str | None:
    for key, value in fields.items():
        lower_key = key.lower()

        if not any(
            fragment in lower_key
            for fragment in ["salary", "gehalt", "vergütung", "compensation"]
        ):
            continue

        if contains_salary_amount(value):
            return value

    patterns = [
        r"\b\d[\d\.\,]*\s*(?:€|EUR)\b(?:.{0,80})?",
        r"\b(?:€|EUR)\s*\d[\d\.\,]*\b(?:.{0,80})?",
    ]

    return find_first_text_match(raw_card_text, patterns)


def extract_salary_ui_prompt_text(fields: dict[str, str]) -> str | None:
    for key, value in fields.items():
        lower_key = key.lower()

        if not any(
            fragment in lower_key
            for fragment in ["salary", "gehalt", "vergütung", "compensation"]
        ):
            continue

        if value and not contains_salary_amount(value):
            return value

    return None


def extract_remote_hint_text(
    fields: dict[str, str],
    raw_card_text: str,
) -> str | None:
    field_value = (
        find_field_by_exact_keys(
            fields,
            [
                "job-item-work-from-home",
                "work-from-home",
                "remote",
                "homeoffice",
                "home-office",
            ],
        )
        or find_field_by_name_fragment(
            fields,
            fragments=[
                "work-from-home",
                "remote",
                "homeoffice",
                "home-office",
                "hybrid",
                "mobile",
            ],
        )
    )

    if field_value:
        return field_value

    patterns = [
        r"\bHomeoffice\b",
        r"\bHome-Office\b",
        r"\bRemote\b",
        r"\bHybrid\b",
        r"\bMobiles Arbeiten\b",
    ]

    return find_first_text_match(raw_card_text, patterns)


def extract_employment_type_hint_text(
    fields: dict[str, str],
    raw_card_text: str,
) -> str | None:
    field_value = find_field_by_name_fragment(
        fields,
        fragments=[
            "employment",
            "contract",
            "arbeitszeit",
            "anstellungsart",
            "job-type",
        ],
    )

    if field_value:
        return field_value

    patterns = [
        r"\bVollzeit\b",
        r"\bTeilzeit\b",
        r"\bFestanstellung\b",
        r"\bBefristet\b",
        r"\bPraktikum\b",
        r"\bWerkstudent\b",
        r"\bFreelance\b",
    ]

    return find_first_text_match(raw_card_text, patterns)


def find_first_text_match(
    value: str,
    patterns: list[str],
) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)

        if match:
            return compact_text(match.group(0))

    return None


def extract_result_card_fields(
    raw_html: str,
    final_url: str,
) -> list[ResultCardFields]:
    article_blocks = iter_article_blocks(raw_html)
    cards: list[ResultCardFields] = []

    for index, article in enumerate(article_blocks, start=1):
        parser = CardParser()
        parser.feed(article.raw_html)

        fields = parser.compact_data_at_fields
        raw_card_text = parser.raw_text

        raw_href = parser.title_href or find_first_job_detail_href(article.raw_html)
        detail_url = urljoin(final_url, raw_href) if raw_href else None

        if detail_url and not is_stepstone_url(detail_url):
            detail_url = None

        title_job_id = extract_stepstone_id_from_url(detail_url)

        cards.append(
            ResultCardFields(
                index=index,
                external_job_id=article.external_job_id,
                title=parser.title,
                company=extract_company(fields),
                location=extract_location(fields),
                detail_url=detail_url,
                raw_href=raw_href,
                card_html_bytes=len(article.raw_html.encode("utf-8")),
                title_id_matches_article_id=title_job_id == article.external_job_id,
                data_at_fields=fields,
                raw_card_text=raw_card_text,
                publication_hint_text=extract_publication_hint_text(
                    fields=fields,
                    raw_card_text=raw_card_text,
                ),
                salary_hint_text=extract_salary_hint_text(
                    fields=fields,
                    raw_card_text=raw_card_text,
                ),
                salary_ui_prompt_text=extract_salary_ui_prompt_text(fields),
                remote_hint_text=extract_remote_hint_text(
                    fields=fields,
                    raw_card_text=raw_card_text,
                ),
                employment_type_hint_text=extract_employment_type_hint_text(
                    fields=fields,
                    raw_card_text=raw_card_text,
                ),
            )
        )

    return cards
