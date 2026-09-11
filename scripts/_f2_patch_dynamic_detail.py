from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"{label}_NOT_UNIQUE:{text.count(old)}")
    return text.replace(old, new, 1)


def patch_multi_origin() -> None:
    path = Path("src/search_intelligence/multi_origin_evidence.py")
    text = path.read_text(encoding="utf-8")
    old = '''    if _has_strong_query_job_identifier(url):
        return True
    # Common rexx/ATS-style root-level vacancy file'''
    new = '''    if _has_strong_query_job_identifier(url):
        return True
    # Opaque jobposting identities are concrete detail paths, but terminal apply
    # actions are deliberately excluded from detail identity.
    if search(r"(?:^|/)jobposting/[a-z0-9_-]{12,}$", path):
        return True
    # Common rexx/ATS-style root-level vacancy file'''
    text = replace_once(text, old, new, "JOBPOSTING_SHAPE")
    path.write_text(text, encoding="utf-8")


def patch_dynamic_route() -> None:
    path = Path("src/connectors/employer_origin_dynamic_route.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from urllib.parse import urlparse\n",
        "from urllib.parse import urlparse, urlunparse\n",
        "DYNAMIC_URLPARSE_IMPORT",
    )

    old = '''_STRONG_DYNAMIC_DETAIL_PATHS = (
    re.compile(r"/(?:jobs?|positions?)/[a-z0-9_-]{2,}/(?:job|position)?/?$", re.IGNORECASE),
    re.compile(r"/jobposting/[a-z0-9_-]{12,}(?:/apply)?/?$", re.IGNORECASE),
)
'''
    new = old + '''_JOBPOSTING_APPLY_PATH = re.compile(
    r"(?P<parent>.*?/jobposting/[a-z0-9_-]{12,})/apply/?$", re.IGNORECASE
)
'''
    text = replace_once(text, old, new, "DYNAMIC_APPLY_REGEX")

    old = '''def _strong_detail_shape(url: str) -> bool:
    if job_detail_url_shape(url):
        return True
    path = urlparse(url).path
    return any(pattern.search(path) for pattern in _STRONG_DYNAMIC_DETAIL_PATHS)


'''
    new = old + '''def _jobposting_parent_detail(url: str) -> str | None:
    parsed = urlparse(url)
    match = _JOBPOSTING_APPLY_PATH.fullmatch(parsed.path or "")
    if match is None:
        return None
    return canonical_url(
        urlunparse(parsed._replace(path=match.group("parent"), query="", fragment=""))
    )


'''
    text = replace_once(text, old, new, "DYNAMIC_PARENT_DETAIL")

    old = '''        if not _strong_detail_shape(url):
            continue
        if not (
            allowed_host(url, allowed_hosts)
            or _same_registered_domain(page_url, url)
            or _trusted_job_host(url)
        ):
            continue
        if url not in values:
            values.append(url)
        if len(values) >= max(0, limit):
            break
'''
    new = '''        if not _strong_detail_shape(url):
            continue
        parent = _jobposting_parent_detail(url)
        candidates = (parent, url) if parent else (url,)
        for candidate in candidates:
            if not candidate or not _public_https(candidate) or non_job_url(candidate):
                continue
            if not _strong_detail_shape(candidate):
                continue
            if not (
                allowed_host(candidate, allowed_hosts)
                or _same_registered_domain(page_url, candidate)
                or _trusted_job_host(candidate)
            ):
                continue
            if candidate not in values:
                values.append(candidate)
            if len(values) >= max(0, limit):
                break
        if len(values) >= max(0, limit):
            break
'''
    text = replace_once(text, old, new, "DYNAMIC_DETAIL_LOOP")

    anchor = "def dynamic_delegated_detail_host(\n"
    function = '''def dynamic_redirected_detail_host(
    *,
    requested_detail_url: str,
    final_url: str,
    delegated_host: str,
) -> str | None:
    """Bind one exact strong redirect emitted by an already-authorized detail host.

    The requested host must be the exact delegated host encoded by dynamic evidence.
    The final URL remains evidence only: it must still be a strong public job URL in
    the same recruiting namespace, and the loaded page must independently pass the
    unchanged genuine-job content proof.
    """

    requested_host = _host(requested_detail_url)
    final_host = _host(final_url)
    expected = str(delegated_host or "").casefold().strip(".")
    if not expected or requested_host != expected or not final_host:
        return None
    if not _public_https(final_url) or not _strong_detail_shape(final_url):
        return None
    if not _same_registered_domain(requested_detail_url, final_url):
        return None
    if not _trusted_job_host(final_url):
        return None
    return final_host


'''
    if "def dynamic_redirected_detail_host(" not in text:
        if text.count(anchor) != 1:
            raise SystemExit(f"DYNAMIC_REDIRECT_ANCHOR_NOT_UNIQUE:{text.count(anchor)}")
        text = text.replace(anchor, function + anchor, 1)

    old = '    "dynamic_delegated_detail_host",\n'
    new = old + '    "dynamic_redirected_detail_host",\n'
    text = replace_once(text, old, new, "DYNAMIC_REDIRECT_EXPORT")
    path.write_text(text, encoding="utf-8")


def patch_acquisition() -> None:
    path = Path("src/connectors/employer_origin_acquisition_v4.py")
    text = path.read_text(encoding="utf-8")
    old = '''    dynamic_delegated_detail_host,
    dynamic_detail_urls,
'''
    new = '''    dynamic_delegated_detail_host,
    dynamic_redirected_detail_host,
    dynamic_detail_urls,
'''
    text = replace_once(text, old, new, "DYNAMIC_REDIRECT_IMPORT")

    old = '''        page = parse_page(
            requested_url=candidate.url,
            html=str(html),
            final_url=str(final_url),
            status_code=int(status_code),
        )
        proof = genuine_job_detail_proof(
'''
    new = '''        page = parse_page(
            requested_url=candidate.url,
            html=str(html),
            final_url=str(final_url),
            status_code=int(status_code),
        )
        dynamic_prefix = f"{_DYNAMIC_DELEGATED_DETAIL_SOURCE}:"
        if (
            candidate.discovery_source.startswith(dynamic_prefix)
            and not allowed_host(page.final_url, effective_allowed_hosts)
        ):
            rebound_host = dynamic_redirected_detail_host(
                requested_detail_url=candidate.url,
                final_url=page.final_url,
                delegated_host=candidate.discovery_source.removeprefix(dynamic_prefix),
            )
            if rebound_host:
                effective_allowed_hosts = tuple(
                    dict.fromkeys([*effective_allowed_hosts, rebound_host])
                )
        proof = genuine_job_detail_proof(
'''
    text = replace_once(text, old, new, "DYNAMIC_REDIRECT_PROOF")
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = Path("tests/test_employer_origin_acquisition_v4_dynamic_route.py")
    text = path.read_text(encoding="utf-8")
    marker = "def test_dynamic_delegated_detail_accepts_same_namespace_strong_redirect()"
    if marker not in text:
        text += '''


def test_dynamic_delegated_detail_accepts_same_namespace_strong_redirect() -> None:
    requested = "https://career-de-example.icims.invalid/jobs/4425/job"
    final = "https://career-eu-example.icims.invalid/jobs/4425/job"
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<script>const detail='{requested}';</script>", ROOT, 200
        if url == requested:
            return job_html(), final, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, requested]
    assert len(jobs) == 1
    assert jobs[0].final_url == final
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_dynamic_delegated_detail_rejects_cross_namespace_redirect() -> None:
    requested = "https://career-de-example.icims.invalid/jobs/4425/job"
    final = "https://career-evil.other.invalid/jobs/4425/job"

    def fetcher(url: str):
        if url == ROOT:
            return f"<script>const detail='{requested}';</script>", ROOT, 200
        if url == requested:
            return job_html(), final, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert jobs == []


def test_dynamic_jobposting_apply_route_prefers_strict_parent_detail() -> None:
    listing = f"https://{HOST}/stellenangebote"
    apply_url = "https://karriere.example.invalid/de/jobposting/abcdef1234567890/apply"
    detail = "https://karriere.example.invalid/de/jobposting/abcdef1234567890"
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<a href='{listing}'>Stellenangebote</a>", ROOT, 200
        if url == listing:
            return f"<script>const apply='{apply_url}';</script>", listing, 200
        if url == detail:
            return (
                "<html><title>Platform Engineer</title><body>"
                "Apply now. Responsibilities and requirements."
                "</body></html>",
                detail,
                200,
            )
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, listing, detail]
    assert len(jobs) == 1
    assert jobs[0].final_url == detail
    assert jobs[0].proof_kind == "job_url_and_job_content"
'''
        path.write_text(text, encoding="utf-8")

    path = Path("tests/test_multi_origin_evidence.py")
    text = path.read_text(encoding="utf-8")
    marker = "def test_jobposting_parent_is_detail_but_apply_action_is_not()"
    if marker not in text:
        text += '''


def test_jobposting_parent_is_detail_but_apply_action_is_not() -> None:
    detail = "https://karriere.example.invalid/de/jobposting/abcdef1234567890"
    assert job_detail_url_shape(detail)
    assert not job_detail_url_shape(detail + "/apply")
'''
        path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_multi_origin()
    patch_dynamic_route()
    patch_acquisition()
    patch_tests()
    print("F2_DYNAMIC_DETAIL_PATCH=READY")


if __name__ == "__main__":
    main()
