"""Conservative employer attribution and revalidated search hints, no network/ML.

A job-shaped URL or a shared brand token never proves employer identity.
Unproved subsidiary/brand relationships require explicit review.
"""
import hashlib
from html.parser import HTMLParser
import json
import re
import unicodedata
from urllib.parse import urlparse

VERSION = "employer_binding.v1"


def identity(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = re.sub(r"[^\w]+", " ", value).strip()
    # Only a trailing legal form is equivalent; never discard identity words.
    value = re.sub(r"(?:\s+(?:gmbh co kg|gmbh co kgaa|gmbh|aktiengesellschaft|ag|kg|kgaa|ug haftungsbeschränkt|inc|ltd))$", "", value)
    return value.strip()


class EvidenceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.json_parts=[]; self.headings=[]; self._json=None; self._heading=None
    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").casefold() == "application/ld+json":
            self._json=[]
        if tag in ("title", "h1"):
            self._heading=[]
    def handle_data(self, data):
        if self._json is not None: self._json.append(data)
        if self._heading is not None: self._heading.append(data)
    def handle_endtag(self, tag):
        if tag == "script" and self._json is not None:
            self.json_parts.append("".join(self._json)); self._json=None
        if tag in ("title", "h1") and self._heading is not None:
            self.headings.append("".join(self._heading)); self._heading=None


def structured(body):
    parser=EvidenceParser(); parser.feed(body[:5_000_000])
    nodes=[]
    def walk(value, depth=0):
        if depth>16 or len(nodes)>=2000: return
        if isinstance(value,dict):
            nodes.append(value)
            for child in value.values(): walk(child,depth+1)
        elif isinstance(value,list):
            for child in value[:2000]: walk(child,depth+1)
    malformed=False
    for text in parser.json_parts[:100]:
        try: walk(json.loads(text))
        except (ValueError,RecursionError): malformed=True
    return nodes,parser.headings,malformed


def has_type(node,kind):
    value=node.get("@type",[])
    return kind in ([value] if isinstance(value,str) else value if isinstance(value,list) else [])


def employer_binding(company_name, root_html, detail_html, root_url, detail_url):
    expected=identity(company_name)
    root_nodes, headings, _=structured(root_html)
    detail_nodes, _, malformed=structured(detail_html)
    def root_organization(node):
        if not has_type(node, "Organization"): return False
        try:
            url = node.get("url")
            return (isinstance(url,str) and urlparse(url).scheme == "https"
                    and urlparse(url).hostname == urlparse(root_url).hostname)
        except ValueError: return False
    organizations=[str(n.get("name", "")) for n in root_nodes if root_organization(n)]
    # Headings must equal the employer name; incidental body mentions do not count.
    root_match=bool(expected and any(identity(n)==expected for n in organizations+headings))
    jobs=[n for n in detail_nodes if has_type(n,"JobPosting")]
    names=[]; complete=bool(jobs)
    for job in jobs:
        if not all(isinstance(job.get(k),str) and job[k].strip() for k in ("title", "description")):
            complete=False
        employer=job.get("hiringOrganization")
        name=employer.get("name") if isinstance(employer,dict) else None
        if not isinstance(name,str) or not name.strip(): complete=False
        else: names.append(name[:300])
    matched=bool(expected and complete and all(identity(n)==expected for n in names))
    reason=("VERIFIED" if root_match and matched and not malformed else
            "EMPLOYER_CONFLICT" if names and any(identity(n)!=expected for n in names) else
            "EMPLOYER_EVIDENCE_MISSING")
    return dict(schema=VERSION,status=reason,expected_name=company_name,
                observed_employers=names,root_identity_matched=root_match,
                root_url=root_url,detail_url=detail_url,
                root_sha256=hashlib.sha256(root_html.encode()).hexdigest(),
                detail_sha256=hashlib.sha256(detail_html.encode()).hexdigest())


def safe_public_url(url):
    try:
        p=urlparse(url)
        return (p.scheme=="https" and bool(p.hostname) and not p.username and not p.password
                and p.port in (None,443) and not p.fragment)
    except (ValueError,TypeError): return False


def recipe_hint(result,company_key,company_name):
    """Only current-schema, identity-bound receipts become hints, never approval."""
    if not isinstance(result,dict): return None
    if result.get("company_key")!=company_key or identity(result.get("company_name"))!=identity(company_name): return None
    layers=result.get("layers",[])
    if not isinstance(layers,list): return None
    recipe=next((x["evidence"].get("search_recipe") for x in layers
                 if isinstance(x,dict) and x.get("layer")=="recipe"
                 and isinstance(x.get("evidence"),dict)),None)
    if not isinstance(recipe,dict) or recipe.get("schema")!="employer_search_recipe.v1": return None
    binding=recipe.get("employer_binding",{})
    if not isinstance(binding,dict): return None
    if binding.get("schema")!=VERSION or binding.get("status")!="VERIFIED" or identity(binding.get("expected_name"))!=identity(company_name): return None
    if recipe.get("company_key")!=company_key: return None
    if not all(safe_public_url(recipe.get(k)) for k in ("root_url","detail_url")): return None
    if any(recipe[k]!=binding.get(k) for k in ("root_url","detail_url")): return None
    return recipe
