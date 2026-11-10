"""Observed ATS routes and finite read plans. These never prove employer identity."""
import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit, unquote, quote

VERSION = 'JAP.URLFinder.ATSContract.0.12.20'
SLUG = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}\Z')
RESERVED = {'www', 'api', 'app', 'help', 'support', 'demo', 'docs', 'certificate'}


def public_url(value):
    if not isinstance(value, str) or len(value) > 4096 or re.search(r'[\s\x00-\x1f\x7f\\]', value):
        return None
    try:
        p = urlsplit(value)
        h = (p.hostname or '').lower().rstrip('.')
        if p.scheme not in ('http', 'https') or not h or p.username or p.password or p.port not in (None, 80, 443):
            return None
        if '.' not in h or h.endswith(('.localhost', '.local', '.internal', '.test', '.invalid')):
            return None
        if not re.fullmatch(r'[a-z0-9.-]+', h):
            return None
        try:
            ipaddress.ip_address(h)
            return None
        except ValueError:
            pass
        decoded = value
        for _ in range(4):
            after = unquote(decoded)
            if re.search(r'[\x00-\x20\x7f\\]', after):
                return None
            if after == decoded:
                break
            decoded = after
        return urlunsplit((p.scheme, h, p.path or '/', p.query, ''))
    except ValueError:
        return None


def identify(value):
    url = public_url(value)
    if not url:
        return None
    p = urlsplit(url); host = p.hostname; path = p.path
    family = tenant = root = None
    scope_review = False
    for suffix in ('jobs.personio.de', 'jobs.personio.com'):
        if host.endswith('.' + suffix):
            candidate = host[:-(len(suffix) + 1)]
            if SLUG.fullmatch(candidate) and candidate not in RESERVED:
                family, tenant, root = 'personio', candidate, 'https://' + host
    if host in ('boards.greenhouse.io', 'job-boards.greenhouse.io'):
        seg = path.strip('/').split('/')[0]
        if SLUG.fullmatch(seg):
            family, tenant, root = 'greenhouse', seg, 'https://' + host + '/' + seg
    if host == 'boards-api.greenhouse.io':
        m = re.fullmatch(r'/v1/boards/([a-zA-Z0-9_-]+)/jobs(?:/\d+)?/?', path)
        if m:
            family, tenant, root = 'greenhouse', m[1], 'https://job-boards.greenhouse.io/' + m[1]
    for suffix in ('dvinci-hr.com', 'dvinci.de', 'dvinci.com'):
        if host.endswith('.' + suffix):
            candidate = host[:-(len(suffix) + 1)]
            if SLUG.fullmatch(candidate) and candidate not in RESERVED:
                family, tenant, root = 'dvinci', candidate, 'https://' + host
                m = re.match(r'^/portal/([a-zA-Z0-9_-]+)(?:/|$)', path)
                if m:
                    root += '/portal/' + m[1]; tenant += '/portal/' + m[1]
                elif re.search(r'/(?:p|portal)/', path):
                    # Localized /de/p/<name> is not documented as /portal/<name>.
                    scope_review = True
    for suffix in ('softgarden.io', 'softgarden.de', 'recruitee.com', 'breezy.hr'):
        if host.endswith('.' + suffix):
            candidate = host[:-(len(suffix) + 1)]
            if SLUG.fullmatch(candidate) and candidate not in RESERVED:
                family = 'softgarden' if suffix.startswith('softgarden') else suffix.split('.')[0]
                tenant, root = candidate, 'https://' + host
    if host == 'join.com':
        m = re.match(r'^/companies/([a-zA-Z0-9_-]+)(?:/|$)', path)
        if m:
            family, tenant, root = 'join', m[1], 'https://join.com/companies/' + m[1]
    if host in ('jobs.smartrecruiters.com','careers.smartrecruiters.com'):
        candidate=path.strip('/').split('/')[0]
        if SLUG.fullmatch(candidate) and candidate.lower() not in RESERVED|{'external-referrals'}:
            family,tenant,root='smartrecruiters',candidate,'https://careers.smartrecruiters.com/'+candidate
    if not family:
        return None
    return dict(family=family, tenant=tenant, tenant_key=family + ':' + tenant,
                observed_url=url, portal_url=root, scope_review=scope_review,
                authority_verified=False, production_admitted=False, contract_version=VERSION)


def inventory_plan(observed_url):
    binding = identify(observed_url)
    if not binding:
        return dict(status='UNSUPPORTED_FAMILY', requests=[], production_admitted=False)
    f = binding['family']; requests = []
    status = 'PUBLIC_HTML_ONLY_NO_API_CREDENTIAL'
    if binding['scope_review']:
        status = 'OBSERVED_SUBPORTAL_FEED_REQUIRED'
    elif f == 'personio':
        requests = [dict(url=binding['portal_url'] + '/xml?language=de', parser='personio_xml')]
    elif f == 'greenhouse':
        requests = [dict(url='https://boards-api.greenhouse.io/v1/boards/' + quote(binding['tenant'], safe='') + '/jobs?content=true', parser='greenhouse_json')]
    elif f == 'dvinci':
        requests = [dict(url=binding['portal_url'] + '/jobPublication/list.json', parser='dvinci_json')]
    elif f == 'smartrecruiters':
        requests = [dict(url='https://api.smartrecruiters.com/v1/companies/'+quote(binding['tenant'],safe='')+'/postings?limit=100&offset=0&destination=PUBLIC',parser='smartrecruiters_inventory')]
    if requests:
        status = 'READ_PLAN_REQUIRES_EMPLOYER_AUTHORITY_AND_RCC_TRANSPORT'
    return dict(status=status, binding=binding, requests=requests, credentials_required=False,
                authority_verified=False, production_admitted=False)


def legacy_slug_url(family, slug):
    """Finite documented shapes; never interpret arbitrary legacy strings as URLs."""
    if not isinstance(slug, str) or not SLUG.fullmatch(slug) or slug.lower() in RESERVED:
        return None
    templates = {'personio': 'https://{}.jobs.personio.com/',
                 'greenhouse': 'https://job-boards.greenhouse.io/{}',
                 'lever': 'https://jobs.lever.co/{}', 'ashby': 'https://jobs.ashbyhq.com/{}',
                 'softgarden': 'https://{}.softgarden.io/', 'recruitee': 'https://{}.recruitee.com/',
                 'smartrecruiters': 'https://jobs.smartrecruiters.com/{}',
                 'join_com': 'https://join.com/companies/{}', 'breezy': 'https://{}.breezy.hr/'}
    return templates[family].format(slug) if family in templates else None
