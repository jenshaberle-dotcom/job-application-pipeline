"""Local entry point for the isolated Hannover TECH registry-to-Factory PoC.

Usage: python -m scripts.run_hannover_tech_registry_poc --help
"""
from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import os
import socket
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

import requests

from src.connectors.hannover_tech_registry_poc import Page, analyze
from src.search_intelligence.hannover_profile_market import PROFILE_SCHEMA


def load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_expansion(path: str) -> dict:
    """Directly import JSON seeds or a manually exported directory CSV."""
    source = Path(path)
    if source.suffix.lower() == ".csv":
        with source.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        return {"schema_version": PROFILE_SCHEMA, "companies": rows}
    payload = load(path)
    if not isinstance(payload, dict):
        raise ValueError("profile_market_seed_object_required")
    return payload


def public_https(url: str) -> None:
    p = urlsplit(url)
    if (p.scheme != "https" or not p.hostname or p.username or p.password
            or p.port not in (None, 443) or len(url) > 2500):
        raise ValueError("https_public_url_required")
    hostname = p.hostname.lower().rstrip(".")
    if (hostname == "localhost" or hostname.endswith((".local", ".internal", ".example"))
            or "." not in hostname):
        raise ValueError("non_public_hostname")
    try:
        addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise OSError("dns_lookup_failed") from exc
    if not addresses:
        raise OSError("dns_empty")
    for result in addresses:
        if not ipaddress.ip_address(result[4][0]).is_global:
            raise ValueError("non_public_dns_address")


def live_getter():
    """Bounded GET-only transport; no credentials, proxies or implicit redirects."""
    session = requests.Session()
    session.trust_env = False

    def get(url: str) -> Page:
        current = url
        for _ in range(4):
            public_https(current)
            try:
                with session.get(
                    current, timeout=(4, 9), stream=True, allow_redirects=False,
                    headers={"User-Agent": "JAP-Hannover-TECH-E2E-POC/0.1",
                             "Accept": "text/html,application/json;q=0.9,*/*;q=0.5"},
                ) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        target = response.headers.get("Location", "")
                        if not target:
                            return Page(current, response.status_code, "")
                        current = urljoin(current, target)
                        continue
                    if int(response.headers.get("Content-Length") or "0") > 2_000_000:
                        raise ValueError("response_size_exceeded")
                    chunks = []
                    total = 0
                    for chunk in response.iter_content(chunk_size=32768):
                        total += len(chunk)
                        if total > 2_000_000:
                            raise ValueError("response_size_exceeded")
                        chunks.append(chunk)
                    body = b"".join(chunks).decode(response.encoding or "utf-8",
                                                     errors="replace")
                    return Page(current, response.status_code, body)
            except requests.RequestException as exc:
                raise OSError(type(exc).__name__) from exc
        raise ValueError("redirect_limit")

    return get


def replay_getter(path: str):
    """Exact immutable request->response fixture. No network access is attempted."""
    rows = load(path)
    if not isinstance(rows, dict):
        raise ValueError("replay_map_required")

    def get(url: str) -> Page:
        record = rows.get(url)
        if not isinstance(record, dict):
            raise OSError("replay_capture_missing")
        return Page(url, int(record["status"]), str(record["body"]))

    return get


def brave_search(api_key: str):
    """Brave candidates only; search results are never ownership proof."""
    def search(name: str) -> list[str]:
        query = quote(f'"{name}" Karriere Jobs Hannover', safe="")
        url = ("https://api.search.brave.com/res/v1/web/search"
               f"?q={query}&count=10&country=DE&search_lang=de")
        public_https(url)
        try:
            result = requests.get(
                url, timeout=12,
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                allow_redirects=False,
            )
            if result.status_code != 200 or len(result.content) > 2_000_000:
                return []
            return [r["url"] for r in result.json().get("web", {}).get("results", [])
                    if isinstance(r, dict) and isinstance(r.get("url"), str)][:10]
        except (requests.RequestException, ValueError, KeyError):
            return []
    return search


def percentage(n: int, denominator: int) -> str:
    return f"{n / denominator * 100:.1f}%" if denominator else "n/a"


def emit(result: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    columns = (
        "company_key", "company_name", "website", "population_segment",
        "sector_labels", "registry_names", "registry_matches",
        "registry_portal_candidates", "portal_candidates",
        "verified_portals", "target_role_jobs_observed",
        "website_evidence", "search_attempted",
        "search_result_count", "status",
    )
    for filename, rows in (
        ("companies.csv", result["companies"]),
        ("long_tail.csv", [r for r in result["companies"] if r["verified_portals"] == 0]),
    ):
        with (output / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    k: ",".join(row[k]) if isinstance(row.get(k), list)
                    else row.get(k, "") for k in columns
                })
    summary = result["summary"]
    total = result["total"]
    lines = [
        "# Hannover TECH: Register to Jobquelle to Connector Factory",
        "",
        f"- Evidenzmodus: {result['evidence_mode']}",
        f"- Vollständige Census-Stichprobe ausgewertet: {not result['sampled']}",
        f"- Hannover-TECH-Kohorte im Input: {result['full_cohort_size']}",
        f"- Tatsächlich ausgewertet: {total}",
        f"- Digest: {result['census_population_digest']}",
        f"- Population: {result['scope']}",
        f"- Alte TECH-Basis: {result['population_audit']['tech_baseline']}",
        f"- Neu ergänzte Arbeitgeber: {result['population_audit']['new_profile_market_candidates']}",
        f"- Rolle: Solution Architect / Lösungsarchitekt (zusätzlich zu bestehenden Profilen)",
        "",
        "| Messpunkt | Unternehmen | Anteil |",
        "|---|---:|---:|",
    ]
    for key, label in (
        ("registry_company_match", "Unternehmen mit Registertreffer"),
        ("registry_portal_candidate", "Register liefert Portalkandidaten"),
        ("any_portal_candidate", "Irgendein Portalkandidat"),
        ("verified_portal", "Eigentümerbezug geprüft"),
        ("verified_registry_portal", "Davon verifizierte Register-Portale"),
        ("delta_verified_without_registry_portal", "Neu: Portal außerhalb der Register"),
        ("long_tail_registry_gap_closed", "Register-Long-Tail erfolgreich geschlossen"),
        ("factory_recipe_built", "Factory-Rezept erstellt"),
        ("factory_extracted", "Factory-Live/Replay-Extraktion erfolgreich"),
        ("employers_with_target_role_jobs", "Arbeitgeber mit Titel-Treffern auf Zielrollen"),
        ("target_role_jobs_observed", "Stellen mit Zielrollen-Titel-Treffern"),
        ("long_tail_registry_gap", "Ohne Registertreffer"),
        ("long_tail_portal_gap", "Ohne verifiziertes Portal"),
        ("long_tail_factory_gap", "Verifiziert, aber kein E2E-Extraktionserfolg"),
    ):
        value = summary[key]
        lines.append(f"| {label} | {value if value is not None else 'n/a'} | "
                     f"{percentage(value, total) if value is not None else 'n/a'} |")
    lines.extend([
        "",
        "## Abdeckung je Teilpopulation",
        "",
        "| Teilpopulation | Unternehmen | Registertreffer | Verifiziert | Extrahiert |",
        "|---|---:|---:|---:|---:|",
    ])
    for segment, data in result["by_segment"].items():
        verified = data["verified_portal"]
        extracted = data["factory_extracted"]
        lines.append(
            f"| {segment} | {data['population']} | {data['register_company_match']} "
            f"| {verified if verified is not None else 'n/a'} "
            f"| {extracted if extracted is not None else 'n/a'} |"
        )
    lines.extend([
        "",
        "## Grenzen",
        "",
        "- Nenner ist die Census-Kohorte, keine Vollerhebung der Tech-Region.",
        "- Registermatches sind Kandidaten, keine bestätigten Arbeitgeber-Portale.",
        "- Ein Factory-Definitionscheck ist keine Runtime-Freigabe.",
        "- Erfolgreiche Extraktion ist ein Smoketest und kein Produktionsnachweis.",
        "- Unerreichbare Quellen sind offen, nicht als arbeitsplatzlos bestätigt.",
        "- Keine DB-Writes, Quellenaktivierung oder Scheduleränderung.",
        "",
        "## Long Tail (erste 30 Firmen)",
        "",
    ])
    gaps = [r for r in result["companies"] if r["verified_portals"] == 0]
    lines += [f"- {row['company_name']}: {row['status']} ({row['website_evidence']})"
              for row in gaps[:30]]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "mode": result["evidence_mode"], "total": total, "summary": summary,
        "files": [str(output / f) for f in
                  ("report.json", "report.md", "companies.csv", "long_tail.csv")],
    }, ensure_ascii=False, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--census", required=True, help="Immutable Census JSON export")
    p.add_argument("--openjobs", required=True, help="OpenJobs companies_v2.json")
    p.add_argument("--boards", required=True, help="Job Board Directory JSON")
    p.add_argument("--catalog", default="contracts/connector-capability-catalog-v1.json")
    p.add_argument(
        "--expanded-companies",
        help="Extra regional employer seeds (JSON or CSV): extends TECH baseline, never replaces it",
    )
    p.add_argument("--output", default="runs/hannover-tech-registry-poc")
    p.add_argument("--approved-websites",
                   help="Optional operator-approved company_key to HTTPS website JSON")
    p.add_argument("--limit", type=int, default=0, help="First N; flagged partial")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="Opt in to bounded public HTTP GET")
    mode.add_argument("--replay", help="Exact offline HTTP response fixture JSON")
    p.add_argument("--brave-search", action="store_true",
                   help="Use BRAVE_API_KEY only with --live")
    a = p.parse_args()
    if a.brave_search and not a.live:
        p.error("--brave-search requires --live")
    key = os.environ.get("BRAVE_API_KEY", "")
    if a.brave_search and not key:
        p.error("BRAVE_API_KEY not set")
    getter = live_getter() if a.live else replay_getter(a.replay) if a.replay else None
    approved = load(a.approved_websites) if a.approved_websites else {}
    if not isinstance(approved, dict):
        p.error("approved websites must be a JSON object")
    result = analyze(
        load(a.census), load(a.openjobs), load(a.boards), load(a.catalog),
        get=getter, approved_websites=approved,
        search=brave_search(key) if a.brave_search else None, limit=a.limit,
        expanded_companies=(
            load_expansion(a.expanded_companies) if a.expanded_companies else None
        ),
    )
    result["evidence_mode"] = (
        "LIVE_PUBLIC_HTTP" if a.live else "OFFLINE_FIXTURE" if a.replay
        else "REGISTRY_MATCH_ONLY"
    )
    emit(result, Path(a.output))


if __name__ == "__main__":
    main()
