"""Supplement observed links with recognized ATS routes and literal widget URLs."""
import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urljoin
from .family_contracts import public_url, identify

class Hints(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []; self.script = None; self.script_type = ''; self.label = None
    def add(self, value, kind, label=''):
        if isinstance(value, str):
            self.rows.append((value, kind, label))
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a' and a.get('href'):
            self.label = [a['href'], []]
        if tag in ('iframe','script') and a.get('src'):
            self.add(a['src'], tag + '_src', a.get('title',''))
        if tag == 'script':
            self.script = []; self.script_type = a.get('type','')
        for key, value in attrs:
            if key in ('data-board-url','data-job-board-url','data-career-url','data-ats-url'):
                self.add(value, 'observed_' + key)
    def handle_data(self, value):
        if self.script is not None:
            self.script.append(value)
        if self.label is not None:
            self.label[1].append(value)
    def handle_endtag(self, tag):
        if tag == 'a' and self.label:
            self.add(self.label[0], 'observed_anchor', ' '.join(self.label[1])); self.label = None
        if tag == 'script' and self.script is not None:
            text = ''.join(self.script)
            # Parse literal strings only. Never eval/execute JS or invent tenant slugs.
            if len(text) <= 262144:
                text = text.replace('\\/', '/')
                for m in re.finditer(r'''["'](https?://[^\s<>"']{1,4096})["']''', text):
                    self.add(m[1], 'observed_script_url_literal')
            self.script = None


def extract(parent_url, body):
    if not public_url(parent_url) or len(body) > 2 * 1024**2:
        raise ValueError('HTML_INPUT_BOUNDARY')
    parser = Hints(); parser.feed(body.decode('utf-8', errors='replace')); parser.close()
    result = {}; digest = hashlib.sha256(body).hexdigest()
    for raw, kind, label in parser.rows[:10000]:
        url = public_url(urljoin(parent_url, raw))
        binding = identify(url) if url else None
        if not binding:
            continue
        # Links may be applications/details. They propose a route; never a portal proof.
        row = result.setdefault(url, dict(url=url, ats=binding, provenance=[],
            authority_verified=False, portal_verified=False, production_admitted=False))
        row['provenance'].append(dict(method=kind, parent_url=parent_url,
                                     body_sha256=digest, label=label[:250]))
    return list(result.values())[:64]


def navigation_links(parent, observed_links, limit=8):
    """Keep recognized board URLs even with opaque/non-career labels."""
    result = []
    for item in observed_links:
        url = public_url(urljoin(parent, item.get('url','')))
        if not url or not identify(url):
            continue
        if re.search(r'/(?:apply|application|login|privacy|data-security)(?:/|$)', url, re.I):
            continue
        result.append(dict(url=url, label=item.get('label',''), rule='OBSERVED_ATS_ROUTE',
                           authority_verified=False, production_admitted=False))
    return list({r['url']:r for r in result}.values())[:limit]
