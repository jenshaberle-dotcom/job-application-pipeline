"""Isolated Hannover TECH registry-to-Factory proof of concept.

No database writes, scheduler changes, connector registration or production activation.
Registry rows are DISCOVERY evidence, never employer-origin authority.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin, urlsplit

from src.connectors.aggressive_factory import advance_candidate
from src.connectors.connector_extraction import (
    AcquisitionResponse,
    ats_plan,
    execute_plan,
    fingerprint_saved_responses,
)

SCHEMA = "jap.hannover_tech_registry_factory_poc.v1"
LEGAL_SUFFIX = re.compile(
    r"\b(gmbh|gbr|ag|se|kg|kgaa|mbh|ug|haftungsbeschrankt|"
    r"gesellschaft|co|holding|inc|ltd|llc|limited)\b"
)
CAREER_WORDS = (
    "karriere", "career", "careers", "jobs", "jobangebote",
    "stellenangebot", "stellenangebote", "vacancies", "bewerbung",
)
ATS_HOSTS = ("greenhouse.io", "lever.co", "myworkdayjobs.com",
             "jobs.personio.de", "jobs.personio.com", "recruitee.com",
             "softgarden.io", "smartrecruiters.com", "ashbyhq.com")
MAX_CANDIDATES = 30


@dataclass(frozen=True)
class Page:
    url: str
    status: int
    body: str


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.heading: list[str] = []
        self._anchor: str | None = None
        self._label: list[str] = []
        self._in_heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "a":
            self._anchor = attrs_dict.get("href")
            self._label = []
        if tag in {"title", "h1"}:
            self._in_heading = True

    def handle_data(self, data: str) -> None:
        if self._anchor is not None:
            self._label.append(data)
        if self._in_heading:
            self.heading.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._anchor is not None:
            self.links.append((self._anchor, " ".join(self._label)))
            self._anchor = None
        if tag in {"title", "h1"}:
            self._in_heading = False


def normalized(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").casefold())
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    return " ".join(LEGAL_SUFFIX.sub(" ", raw).split())


def key_of(value: object) -> str:
    return normalized(value).replace(" ", "")


def clean_url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    try:
        p = urlsplit(value.strip())
        if p.scheme != "https" or not p.hostname or p.username or p.password:
            return ""
        if p.port not in (None, 443):
            return ""
        return "https://" + p.hostname.lower() + (p.path.rstrip("/") or "/")
    except ValueError:
        return ""


def host(value: object) -> str:
    try:
        p = urlsplit(str(value or ""))
        return (p.hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def website(row: dict) -> str:
    for field in ("employer_website", "company_website", "website", "homepage_url"):
        url = clean_url(row.get(field))
        if url:
            return url
    # Actual connector_mass_census emits a list named 'websites'.
    # Never choose arbitrarily among several corporate domains.
    raw = row.get("websites", [])
    if isinstance(raw, list):
        valid = sorted({value for item in raw if (value := clean_url(item))})
        if len(valid) == 1:
            return valid[0]
    return ""


def hannover_tech(row: dict) -> bool:
    """Honor explicit geography/cohort PAIRS; never invent a Cartesian product."""
    memberships = row.get("scope_memberships")
    pairs: list[tuple[str, str]] = []
    if isinstance(memberships, list) and memberships:
        for item in memberships:
            if isinstance(item, dict):
                pairs.append((
                    str(item.get("geography") or item.get("region") or "").upper(),
                    str(item.get("cohort") or item.get("sector") or "").upper(),
                ))
            elif isinstance(item, str):
                parts = item.upper().replace(":", "|").split("|")
                if len(parts) == 2:
                    pairs.append((parts[0], parts[1]))
    else:
        # Older single-geography exports without scope_memberships.
        geographies = row.get("geographies", [])
        cohorts = row.get("cohorts", [])
        if isinstance(geographies, str):
            geographies = [geographies]
        if isinstance(cohorts, str):
            cohorts = [cohorts]
        if isinstance(geographies, list) and isinstance(cohorts, list):
            pairs = [(str(g).upper(), str(c).upper())
                     for g in geographies for c in cohorts]
    return any(
        g.replace(" ", "_") in {"REGION_HANNOVER", "HANNOVER", "HANNOVER_REGION"}
        and c == "TECH" for g, c in pairs
    )


def population(census: dict) -> list[dict]:
    if not isinstance(census.get("candidates"), list):
        raise ValueError("census_candidates_required")
    rows: dict[str, dict] = {}
    for record in census["candidates"]:
        if not isinstance(record, dict) or not hannover_tech(record):
            continue
        company_key = str(record.get("company_key") or "").strip().casefold()
        if not company_key or not record.get("company_name"):
            raise ValueError("hannover_tech_identity_missing")
        if company_key in rows:
            raise ValueError("hannover_tech_duplicate_company_key")
        rows[company_key] = record
    if not rows:
        raise ValueError("no_hannover_tech_membership_found_fail_closed")
    return [rows[k] for k in sorted(rows)]


def catalog_indices(openjobs: list, boards: list) -> tuple[dict, dict]:
    """Exact normalized name or exact independently observed corporate host."""
    by_name: dict[str, list[dict]] = {}
    by_website: dict[str, list[dict]] = {}

    for record in openjobs:
        if not isinstance(record, dict) or not record.get("name"):
            continue
        item = {
            "registry": "OpenJobs",
            "name": str(record["name"]),
            "website": clean_url(record.get("website")),
            "urls": [u for u in (record.get("ats_links") or [])
                     if isinstance(u, str) and clean_url(u)],
        }
        by_name.setdefault(key_of(item["name"]), []).append(item)
        if host(item["website"]):
            by_website.setdefault(host(item["website"]), []).append(item)

    for record in boards:
        if not isinstance(record, dict) or not record.get("company"):
            continue
        item = {
            "registry": "JobBoardDirectory",
            "name": str(record["company"]),
            "website": "",
            "urls": [record["board_url"]] if clean_url(record.get("board_url")) else [],
            "api_url": clean_url(record.get("api_url")),
            "platform": str(record.get("platform") or ""),
        }
        by_name.setdefault(key_of(item["name"]), []).append(item)
    return by_name, by_website


def matches_for(row: dict, indices: tuple[dict, dict]) -> list[dict]:
    by_name, by_website = indices
    name_key = key_of(row["company_name"])
    company_host = host(website(row))
    found: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    candidates = [(item, "EXACT_NAME") for item in by_name.get(name_key, [])]
    if company_host:
        candidates += [(item, "EXACT_WEBSITE_HOST")
                       for item in by_website.get(company_host, [])]
    for item, method in candidates:
        identity = (item["registry"], item["name"], item["website"])
        if identity not in seen:
            found.append({**item, "match_method": method})
            seen.add(identity)
    return found


def family(url: str) -> str:
    p = urlsplit(url)
    h = (p.hostname or "").lower()
    if h in {"boards.greenhouse.io", "job-boards.greenhouse.io",
             "boards-api.greenhouse.io"}:
        return "greenhouse"
    if h in {"jobs.lever.co", "api.lever.co", "api.eu.lever.co"}:
        return "lever"
    if h.endswith(".myworkdayjobs.com"):
        return "workday"
    if h.endswith(".jobs.personio.de") or h.endswith(".jobs.personio.com"):
        return "personio"
    if any(h == x or h.endswith("." + x) for x in ATS_HOSTS):
        return "other_ats"
    return "generic"


def board_url(url: str) -> str:
    """Reduce observed ATS job URLs to their tenant board; no slug inference."""
    p = urlsplit(clean_url(url))
    parts = [s for s in p.path.split("/") if s]
    fam = family(url)
    if fam == "greenhouse" and p.hostname != "boards-api.greenhouse.io" and parts:
        return f"https://{p.hostname}/{parts[0]}"
    if fam == "lever" and p.hostname == "jobs.lever.co" and parts:
        return f"https://jobs.lever.co/{parts[0]}"
    if fam == "workday" and parts:
        return f"https://{p.hostname}/{parts[0]}"
    if fam == "personio":
        return f"https://{p.hostname}/"
    return clean_url(url)


def api_for(url: str) -> str:
    p = urlsplit(board_url(url))
    parts = [s for s in p.path.split("/") if s]
    fam = family(url)
    if not parts or not re.fullmatch(r"[A-Za-z0-9_-]+", parts[0]):
        return ""
    if fam == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{parts[0]}/jobs?content=true"
    if fam == "lever":
        return f"https://api.lever.co/v0/postings/{parts[0]}?mode=json"
    return ""


def related(candidate: str, observed_link: str) -> bool:
    """The actual link must point to that tenant, not merely the same ATS vendor."""
    a = urlsplit(board_url(candidate))
    b = urlsplit(clean_url(observed_link))
    if not a.hostname or not b.hostname or a.hostname != b.hostname:
        return False
    if family(candidate) != "generic" and a.path in ("", "/"):
        # An ATS vendor root is never evidence for a specific tenant.
        return False
    prefix = a.path.rstrip("/")
    return b.path == prefix or b.path.startswith(prefix + "/")


def parse_links(page: Page) -> tuple[list[str], str]:
    parser = Links()
    parser.feed(page.body[:1_000_000])
    links = []
    for href, label in parser.links:
        resolved = clean_url(urljoin(page.url, href))
        if not resolved:
            continue
        if (family(resolved) != "generic"
                or any(word in (href + " " + label).casefold()
                       for word in CAREER_WORDS)):
            links.append(resolved)
    return sorted(set(links)), normalized(" ".join(parser.heading))


def candidate_set(records: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in records:
        for url in item["urls"]:
            canonical = board_url(url)
            if not canonical:
                continue
            entry = result.setdefault(canonical, {
                "board_url": canonical,
                "family": family(canonical),
                "registry_sources": [],
                "discovered_on_official_site": False,
                "search_discovered": False,
            })
            if item["registry"] not in entry["registry_sources"]:
                entry["registry_sources"].append(item["registry"])
    return result


def _site_identity_verified(row: dict, records: list[dict],
                            approved: dict[str, str], heading: str) -> tuple[bool, str]:
    site = website(row)
    key = str(row["company_key"]).casefold()
    if not site:
        return False, "NO_COMPANY_WEBSITE"
    if host(approved.get(key)) == host(site):
        return True, "OPERATOR_APPROVED_WEBSITE"
    if not heading or key_of(row["company_name"]) not in key_of(heading):
        return False, "OFFICIAL_SITE_IDENTITY_UNPROVEN"
    for record in records:
        if (record["registry"] == "OpenJobs"
                and record["match_method"] == "EXACT_NAME"
                and host(record["website"]) == host(site)):
            return True, "CORROBORATED_NAME_DOMAIN_AND_SITE_TITLE"
    return False, "OFFICIAL_SITE_IDENTITY_UNPROVEN"


def _collect_site_links(row: dict, records: list[dict],
                        get: Callable[[str], Page],
                        approved: dict[str, str],
                        search_results: list[str]) -> tuple[list[str], bool, str, list[str]]:
    site = website(row)
    if not site:
        reason = ("AMBIGUOUS_CENSUS_WEBSITES" if len(row.get("websites", [])) > 1
                  else "NO_COMPANY_WEBSITE")
        return [], False, reason, []
    links: set[str] = set()
    captures: set[str] = set()
    heading = ""
    attempts = [site]
    # A search result on the corporate hostname can reveal a hidden career landing page.
    attempts += [x for x in search_results if host(x) == host(site)][:2]
    checked = set()
    for url in attempts[:3]:
        if url in checked:
            continue
        checked.add(url)
        try:
            response = get(url)
        except (OSError, ValueError, RuntimeError):
            continue
        if response.status != 200 or host(response.url) != host(site):
            continue
        captures.add("site-html-sha256:" + hashlib.sha256(
            response.body.encode("utf-8")).hexdigest())
        parsed, page_heading = parse_links(response)
        heading += " " + page_heading
        links.update(parsed)
    verified, reason = _site_identity_verified(row, records, approved, heading)
    return sorted(links), verified, reason, sorted(captures)


def _factory_e2e(row: dict, candidate: dict, catalog: dict,
                 census_digest: str, get: Callable[[str], Page]) -> dict:
    board = candidate["board_url"]
    fam = candidate["family"]
    api = api_for(board)
    if not api:
        return {"status": "UNSUPPORTED_PROVIDER", "reason": "no_supported_public_json_api"}
    authorized = {"https://" + urlsplit(board).hostname,
                  "https://" + urlsplit(api).hostname}
    if host(website(row)):
        authorized.add("https://" + host(website(row)))
        authorized.add("https://www." + host(website(row)))
    origins = tuple(sorted(authorized))
    try:
        initial = ats_plan("a" * 64, board, api, origins, fam)
        first = get(api)
        captured = AcquisitionResponse(api, first.status, first.body)
        tags = fingerprint_saved_responses(initial, (captured,))
        if not tags:
            return {"status": "ZERO_OR_UNSUPPORTED_RECORDS",
                    "reason": "no_qualifiable_nonempty_job_inventory"}
        source = {
            "company_key": str(row["company_key"]).casefold(),
            "origin_url": board,
            "source_type": "employer_origin_ats_backed_career_site",
            "evidence_ids": candidate.get("evidence_ids", []),
            "fingerprint_tags": list(tags),
            "market_sensor_only": False,
        }
        result = advance_candidate(source, catalog_payload=catalog,
                                   census_digest=census_digest)
        status = result["factory_disposition"]
        if status != "qualified_inactive":
            return {"status": "FACTORY_GAP", "disposition": status,
                    "reason": result.get("reason")}
        definition = {
            "recipe_id": result["recipe_id"],
            "definition_status": result["definition_status"],
            "definition_proof_id": result["qualification_proof_id"],
            "persistable_definition": result.get("persistable_definition"),
            "runtime_admitted": False,
            "production_activated": False,
        }
        try:
            plan = ats_plan(result["recipe_id"], board, api, origins, fam)
            # Real existing runtime interpreter, with no production admission.
            def read_response(url: str) -> AcquisitionResponse:
                if url == api:
                    return captured
                page = get(url)
                return AcquisitionResponse(url, page.status, page.body)
            jobs = execute_plan(plan, read_response)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
            return {**definition, "status": "EXTRACTION_GAP",
                    "reason": type(error).__name__ + ":" + str(error)[:150]}
        return {
            **definition,
            "status": "EXTRACTION_PASS",
            "job_count": len(jobs),
            "job_sample": [{"title": job.title, "url": job.source_url}
                           for job in jobs[:3]],
        }
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        return {"status": "EXTRACTION_GAP", "reason": type(error).__name__ +
                ":" + str(error)[:150]}


def analyze(census: dict, openjobs: list, boards: list, catalog: dict,
            *, get: Callable[[str], Page] | None = None,
            approved_websites: dict[str, str] | None = None,
            search: Callable[[str], list[str]] | None = None,
            limit: int = 0) -> dict:
    cohort = population(census)
    full_count = len(cohort)
    if limit:
        if limit < 1:
            raise ValueError("limit_must_be_positive")
        cohort = cohort[:limit]
    digest = hashlib.sha256(
        json.dumps(cohort, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    indices = catalog_indices(openjobs, boards)
    rows = []
    for row in cohort:
        matches = matches_for(row, indices)
        candidates = candidate_set(matches)
        # First inspect the corporate website. Pay for search only if still unresolved.
        official_links, site_ok, site_reason, site_captures = (
            _collect_site_links(row, matches, get,
                                approved_websites or {}, [])
            if get is not None else ([], False, "NOT_CHECKED_OFFLINE", [])
        )
        has_direct_origin = site_ok and any(
            family(link) != "generic" for link in official_links
        )
        search_hits: list[str] = []
        search_attempted = False
        if get is not None and search is not None and not has_direct_origin:
            search_attempted = True
            search_hits = search(str(row["company_name"]))[:10]
            for link in search_hits:
                canonical = board_url(link)
                if not canonical or family(canonical) == "generic":
                    continue
                entry = candidates.setdefault(canonical, {
                    "board_url": canonical, "family": family(canonical),
                    "registry_sources": [], "discovered_on_official_site": False,
                    "search_discovered": False,
                })
                entry["search_discovered"] = True
            # Search-supplied corporate pages remain discovery only until verified.
            if any(host(x) == host(website(row)) for x in search_hits):
                extra, extra_ok, extra_reason, extra_captures = _collect_site_links(
                    row, matches, get, approved_websites or {}, search_hits
                )
                official_links = sorted(set(official_links + extra))
                site_captures = sorted(set(site_captures + extra_captures))
                if extra_ok:
                    site_ok, site_reason = True, extra_reason
        for link in official_links:
            canonical = board_url(link)
            if not canonical:
                continue
            if family(canonical) == "generic" and host(canonical) != host(website(row)):
                continue
            entry = candidates.setdefault(canonical, {
                "board_url": canonical, "family": family(canonical),
                "registry_sources": [], "discovered_on_official_site": False,
                "search_discovered": False,
            })
            entry["discovered_on_official_site"] = True
        verified = []
        for entry in candidates.values():
            ownership_links = [link for link in official_links
                               if related(entry["board_url"], link)]
            entry["ownership_verified"] = bool(
                site_ok and entry["family"] != "generic" and ownership_links
            )
            entry["ownership_link_urls"] = ownership_links
            entry["evidence_ids"] = (
                ["official-career-link-sha256:" + hashlib.sha256(
                    link.encode("utf-8")).hexdigest() for link in ownership_links]
                + site_captures
                if entry["ownership_verified"] else []
            )
            if entry["ownership_verified"]:
                verified.append(entry)
        factory = []
        if get is not None:
            for candidate in sorted(verified, key=lambda x: x["board_url"])[:MAX_CANDIDATES]:
                factory.append({"board_url": candidate["board_url"],
                                **_factory_e2e(row, candidate, catalog, digest, get)})
        registry_names = sorted({m["registry"] for m in matches})
        status = (
            "EXTRACTED" if any(f["status"] == "EXTRACTION_PASS" for f in factory)
            else "VERIFIED_FACTORY_GAP" if verified
            else "PORTAL_CANDIDATE_UNVERIFIED" if candidates
            else "REGISTERED_WITHOUT_PORTAL" if matches
            else "NO_REGISTER_MATCH"
        )
        rows.append({
            "company_key": str(row["company_key"]),
            "company_name": str(row["company_name"]),
            "website": website(row),
            "registry_matches": len(matches),
            "registry_names": registry_names,
            "registry_portal_candidates": sum(
                bool(c["registry_sources"]) for c in candidates.values()),
            "portal_candidates": len(candidates),
            "verified_portals": len(verified),
            "website_evidence": site_reason,
            "search_attempted": search_attempted,
            "search_result_count": len(search_hits),
            "status": status,
            "candidates": sorted(candidates.values(), key=lambda x: x["board_url"]),
            "factory": factory,
        })
    def count(predicate: Callable[[dict], bool]) -> int:
        return sum(bool(predicate(item)) for item in rows)
    return {
        "schema_version": SCHEMA,
        "scope": "REGION_HANNOVER:TECH",
        "census_population_digest": digest,
        "sampled": len(cohort) != full_count,
        "full_cohort_size": full_count,
        "live_evidence_checked": get is not None,
        "total": len(rows),
        "summary": {
            "registry_company_match": count(lambda x: x["registry_matches"] > 0),
            "registry_portal_candidate": count(lambda x: x["registry_portal_candidates"] > 0),
            "any_portal_candidate": count(lambda x: x["portal_candidates"] > 0),
            "verified_portal": count(lambda x: x["verified_portals"] > 0),
            "verified_registry_portal": count(lambda x: any(
                candidate["ownership_verified"] and candidate["registry_sources"]
                for candidate in x["candidates"])),
            "delta_verified_without_registry_portal": count(lambda x:
                x["verified_portals"] > 0 and x["registry_portal_candidates"] == 0),
            "long_tail_registry_gap_closed": count(lambda x:
                x["registry_matches"] == 0 and x["verified_portals"] > 0),
            "factory_recipe_built": count(lambda x: any(
                f.get("recipe_id") for f in x["factory"])),
            "factory_extracted": count(
                lambda x: any(f["status"] == "EXTRACTION_PASS" for f in x["factory"])),
            "long_tail_registry_gap": count(lambda x: x["registry_matches"] == 0),
            "long_tail_portal_gap": (count(lambda x: x["verified_portals"] == 0)
                                     if get is not None else None),
            "long_tail_factory_gap": (count(
                lambda x: x["verified_portals"] > 0 and not any(
                    f["status"] == "EXTRACTION_PASS" for f in x["factory"]))
                if get is not None else None),
        },
        "companies": rows,
    }
