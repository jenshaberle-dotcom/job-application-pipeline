"""Pure client-code evidence for one explicit GET API-host delegation.

This module performs no network I/O. It recognizes only a narrow Webpack/Next.js
shape where an already-observed same-host route script performs a GET to a
job-context relative path whose API base is returned by one imported module export.
The imported export must resolve to one literal HTTPS base in an observed same-host
script. Dynamic expressions, POST calls, ambiguous module/export bindings and
cross-host script evidence fail closed.

Recognition is deliberately separate from authority. Callers must still prove that
the browser page itself is authorized before the resolved API response host may be
used by runtime job-record proof.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable
from urllib.parse import urlparse


_JOB_CONTEXT_MARKERS = (
    "career",
    "careers",
    "job",
    "jobs",
    "opening",
    "openings",
    "position",
    "positions",
    "requisition",
    "requisitions",
    "vacancy",
    "vacancies",
)
_IDENTIFIER = r"[A-Za-z_$][A-Za-z0-9_$]*"
_GET_TEMPLATE = re.compile(
    rf"\.get\(\s*`\$\{{\(0,(?P<var>{_IDENTIFIER})\.(?P<export>{_IDENTIFIER})\)\(\)\}}"
    r"(?P<path>/[^`\r\n]{1,512})`",
)


@dataclass(frozen=True)
class ClientCodeApiDelegation:
    """One fully resolved explicit client-code GET delegation hypothesis."""

    page_url: str
    route_script_url: str
    request_method: str
    endpoint_path: str
    api_base_url: str
    api_url: str
    api_host: str
    module_id: str
    export_name: str


def _host(value: str) -> str:
    return (urlparse(str(value or "")).hostname or "").casefold().strip(".")


def _normalized_hosts(values: Iterable[str]) -> set[str]:
    return {_host(f"https://{str(item).strip('.')}") for item in values if str(item).strip()}


def _same_host_https_script(*, page_url: str, script_url: str) -> bool:
    page = urlparse(page_url)
    script = urlparse(script_url)
    return bool(
        page.scheme.casefold() == "https"
        and script.scheme.casefold() == "https"
        and _host(page_url)
        and _host(page_url) == _host(script_url)
        and not script.username
        and not script.password
        and script.path.casefold().endswith(".js")
    )


def _jobish_relative_path(value: str) -> bool:
    path = str(value or "").strip()
    if (
        not path.startswith("/")
        or path.startswith("//")
        or "\\" in path
        or "?" in path
        or "#" in path
        or len(path) > 512
    ):
        return False
    lowered = path.casefold()
    return any(marker in lowered for marker in _JOB_CONTEXT_MARKERS)


def _static_https_base(value: str) -> str | None:
    parsed = urlparse(str(value or "").strip())
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return None
    return str(value).rstrip("/")


def _module_ids_for_var(route_script_body: str, variable: str) -> tuple[str, ...]:
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_$]){re.escape(variable)}\s*=\s*{_IDENTIFIER}\((?P<module>[0-9]+)\)"
    )
    return tuple(dict.fromkeys(match.group("module") for match in pattern.finditer(route_script_body)))


def _literal_base_for_export(
    *,
    module_id: str,
    export_name: str,
    script_body: str,
) -> tuple[str, ...]:
    marker = re.compile(rf"(?:^|[,{{]){re.escape(module_id)}\s*:\s*\(")
    bases: list[str] = []

    for match in marker.finditer(script_body):
        window = script_body[match.start() : match.start() + 8_000]
        export_maps = re.finditer(
            rf"{_IDENTIFIER}\.d\({_IDENTIFIER},\{{(?P<body>[^}}]{{1,1200}})\}}\)",
            window,
        )
        for export_map in export_maps:
            body = export_map.group("body")
            export_entry = re.search(
                rf"(?:^|,)\s*{re.escape(export_name)}\s*:\s*\(\)\s*=>\s*(?P<local>{_IDENTIFIER})(?:\s*,|\s*$)",
                body,
            )
            if export_entry is None:
                continue
            local = export_entry.group("local")
            literal = re.search(
                rf"(?:let|const|var)\s+{re.escape(local)}\s*=\s*\(\)\s*=>\s*[\"'](?P<base>https://[^\"']{{1,512}})[\"']",
                window,
            )
            if literal is None:
                continue
            base = _static_https_base(literal.group("base"))
            if base and base not in bases:
                bases.append(base)

    return tuple(bases)


def explicit_client_code_api_get_delegation(
    *,
    page_url: str,
    route_script_url: str,
    route_script_body: str,
    module_scripts: Iterable[tuple[str, str]],
) -> ClientCodeApiDelegation | None:
    """Resolve exactly one explicit same-page client-code GET API delegation.

    The function recognizes evidence only. It does not by itself authorize the page
    or the API host and performs no fetching.
    """

    if not _same_host_https_script(page_url=page_url, script_url=route_script_url):
        return None

    module_sources = [
        (str(url), str(body))
        for url, body in module_scripts
        if _same_host_https_script(page_url=page_url, script_url=str(url))
    ]

    resolved: list[ClientCodeApiDelegation] = []
    seen: set[tuple[str, str, str, str]] = set()

    for call in _GET_TEMPLATE.finditer(str(route_script_body or "")):
        endpoint_path = call.group("path")
        if not _jobish_relative_path(endpoint_path):
            continue

        variable = call.group("var")
        export_name = call.group("export")
        module_ids = _module_ids_for_var(route_script_body, variable)
        if len(module_ids) != 1:
            continue
        module_id = module_ids[0]

        bases: list[str] = []
        for _script_url, script_body in module_sources:
            for base in _literal_base_for_export(
                module_id=module_id,
                export_name=export_name,
                script_body=script_body,
            ):
                if base not in bases:
                    bases.append(base)
        if len(bases) != 1:
            continue

        api_base_url = bases[0]
        api_url = f"{api_base_url}{endpoint_path}"
        parsed_api = urlparse(api_url)
        if parsed_api.scheme.casefold() != "https" or not parsed_api.hostname:
            continue

        identity = (module_id, export_name, endpoint_path, api_url)
        if identity in seen:
            continue
        seen.add(identity)
        resolved.append(
            ClientCodeApiDelegation(
                page_url=page_url,
                route_script_url=route_script_url,
                request_method="GET",
                endpoint_path=endpoint_path,
                api_base_url=api_base_url,
                api_url=api_url,
                api_host=_host(api_url),
                module_id=module_id,
                export_name=export_name,
            )
        )

    if len(resolved) != 1:
        return None
    return resolved[0]


def client_code_delegated_response_host(
    delegation: ClientCodeApiDelegation | None,
    *,
    allowed_page_hosts: Iterable[str],
) -> str | None:
    """Return the API host only when the delegation originates on an authorized page."""

    if delegation is None:
        return None
    allowed = _normalized_hosts(allowed_page_hosts)
    page_host = _host(delegation.page_url)
    route_host = _host(delegation.route_script_url)
    if not page_host or page_host not in allowed or route_host != page_host:
        return None
    return delegation.api_host or None


__all__ = [
    "ClientCodeApiDelegation",
    "client_code_delegated_response_host",
    "explicit_client_code_api_get_delegation",
]
