"""Provider-free discovery hints and reproducible cohort evaluation.

Observed links, family recognition and similarity never confer employer authority.
Only the existing fresh employer/job proof can qualify a connector recipe.
"""
from collections import Counter, defaultdict
from hashlib import sha256
import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from .ats_provider_registry import recognize_ats_provider

VERSION = "factory_learning.v1"


def public_url(value):
    try:
        p = urlsplit(str(value))
        host = (p.hostname or "").lower()
        if p.scheme != "https" or p.username or p.password or p.port not in (None, 443):
            return None
        if not host or "." not in host or host.endswith((".local", ".internal", ".localhost")):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return urlunsplit(("https", p.netloc.lower(), p.path or "/", p.query, ""))
    except ValueError:
        return None


def link_features(url):
    p = urlsplit(url)
    recognition = recognize_ats_provider(url)
    path = p.path.lower()
    role = ("job_detail" if re.search(r"/(?:job|jobs|position|positions|stellenangebot)/[^/]+", path)
            else "career_portal" if recognition or re.search(r"career|karriere|jobs|stellen", url.lower())
            else "company_site")
    return dict(url=url, host=p.hostname, role=role,
                family=recognition.provider if recognition else "unknown_web",
                employer_verified=False)


def discovery_plan(observation, *, semantic_scores=None):
    """Keep source provenance; optional local-model scores only break ranking ties."""
    urls = sorted({u for x in observation.get("websites", []) if (u := public_url(x))})
    nodes = [link_features(u) for u in urls]
    scores = semantic_scores or {}
    # Prefer company roots for attribution, then career surfaces, then detail links.
    priorities = {"company_site": 0, "career_portal": 1, "job_detail": 2}
    nodes.sort(key=lambda n: (priorities[n["role"]],
                             -max(-1, min(1, float(scores.get(n["url"], 0)))), n["url"]))
    return dict(schema=VERSION, company_key=observation["company_key"],
                nodes=nodes, edges=[dict(kind="observed_for", company_key=observation["company_key"],
                    url=n["url"], authority="hint", sources=sorted({str(x.get("source", "unknown"))
                    for x in observation.get("observations", [])})) for n in nodes],
                ordered_urls=[n["url"] for n in nodes],
                ranking="local_semantic_hint" if semantic_scores else "structural_baseline",
                automatic_identity_approval=False)


def result_urls(value):
    """Bounded traversal of saved evidence, including URL-shape dictionaries."""
    found = set()
    def visit(v, depth=0):
        if depth > 16:
            return
        if isinstance(v, str):
            u = public_url(v)
            if u:
                found.add(u)
        elif isinstance(v, dict):
            host = v.get("host") or v.get("hostname")
            if host:
                u = public_url("https://" + str(host) + str(v.get("path") or "/"))
                if u:
                    found.add(u)
            for item in v.values():
                visit(item, depth + 1)
        elif isinstance(v, list):
            for item in v:
                visit(item, depth + 1)
    visit(value)
    return sorted(found)


def learning_receipt(observation, result, state):
    plan = discovery_plan(observation)
    nodes = [link_features(u) for u in result_urls(result)]
    families = sorted({n["family"] for n in nodes + plan["nodes"] if n["family"] != "unknown_web"})
    return dict(schema=VERSION, discovery=plan, families=families or ["unknown_web"],
                failure_stage=result.get("first_failure_layer") or state,
                failure_reason=result.get("first_failure_reason") or result.get("reason") or state,
                # Assessment proves a sample, not an exhaustive inventory or activation.
                inventory_completeness="not_proven", sources_activated=0, jobs_imported=0,
                qualified=state == "QUALIFIED", strategy_candidates=[
                    dict(family=f, strategy="existing_provider_adapter", tenant_transfer=False,
                         fresh_employer_proof_required=True) for f in families])


def coverage_state(*, fetched, exhausted, jobs, error=None):
    if error or not fetched:
        return "FETCH_FAILED"
    if not exhausted:
        return "PARTIAL_INVENTORY"
    return "COMPLETE_NONEMPTY" if jobs else "VERIFIED_EMPTY"


def navigation_priority(url, relation=""):
    """Local baseline; no model or external lookup required."""
    path = urlsplit(url).path.lower()
    if relation == "detail":
        return 0
    if re.search(r"career|karriere|jobs|stellen|vacanc|position", path):
        return 1
    return 2


def evaluate(rows, previous=(), sample_per_cohort=3):
    """Compare stable company identities, and freeze examples independently of row order."""
    def indexed(items):
        out = {}
        for observation, state, result in items:
            key = observation["company_key"]
            if key in out:
                raise ValueError("DUPLICATE_EMPLOYER_IDENTITY")
            out[key] = (observation, state, result)
        return out
    current, old = indexed(rows), indexed(previous)
    groups = defaultdict(list)
    for key, (observation, state, result) in current.items():
        receipt = learning_receipt(observation, result, state)
        for family in receipt["families"]:
            groups[(family, receipt["failure_stage"], receipt["failure_reason"])].append(key)
    cohorts = []
    for (family, stage, reason), keys in groups.items():
        examples = sorted(keys, key=lambda k: sha256(k.encode()).hexdigest())[:sample_per_cohort]
        cohorts.append(dict(family=family, stage=stage, reason=reason, affected_employers=len(keys),
                            sample_keys=examples, priority_basis="affected_employers; yield not yet measured"))
    success = {k for k, v in current.items() if v[1] == "QUALIFIED"}
    prior_success = {k for k, v in old.items() if v[1] == "QUALIFIED"}
    shared = current.keys() & old.keys()
    return dict(schema=VERSION, total=len(current), states=dict(Counter(v[1] for v in current.values())),
                reusable_family_recipes=sorted({family for (family, stage, reason) in groups
                    if stage == "QUALIFIED" and family != "unknown_web"}),
                cohorts=sorted(cohorts, key=lambda c: (-c["affected_employers"], c["family"], c["stage"], c["reason"])),
                comparison=dict(shared=len(shared), added=sorted(current.keys()-old.keys()),
                    missing=sorted(old.keys()-current.keys()), retained=sorted(success & prior_success),
                    new_qualifications=sorted((success-prior_success) & shared),
                    regressions=sorted((prior_success-success) & shared)),
                qualification_is_activation=False, personal_location_filter=False)
