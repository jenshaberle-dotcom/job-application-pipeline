"""Observed HTML evidence. No JS execution, model suggestions or name-only authority."""
import json,re
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from .family_contracts import public_url,identify
from .discovery_candidate import extract
from .identity_contract import matches_name,tokens,structured_match

LEGAL=re.compile(r'impressum|imprint|legal[- /_]*(?:notice|disclosure)',re.I)
CAREER=re.compile(r'jobs?|career|karriere|stellen|vacancies|working|arbeiten',re.I)
WEB_LABEL=re.compile(r'^(?:website|webseite|web site|homepage|unternehmenswebsite|company website|zur website)$',re.I)

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[];self.anchor=None;self.hidden=0;self.heading=0;self.headings=[]
        self.text=[];self.current=[];self.blocks=[];self.script=None;self.jsonld=[]
    def flush(self):
        if self.current:self.blocks.append(' '.join(self.current));self.current=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('p','div','li','section','article','br','h1','h2','h3','tr','td'):self.flush()
        if tag in ('script','style'):self.hidden+=1
        if tag=='script' and a.get('type','').lower()=='application/ld+json':self.script=[]
        if tag in ('h1','h2','h3','title'):self.heading+=1
        if tag=='a' and a.get('href'):self.anchor=[a['href'],[]]
    def handle_endtag(self,tag):
        if tag=='script' and self.script is not None:
            try:self.jsonld.append(json.loads(''.join(self.script)))
            except (ValueError,RecursionError):pass
            self.script=None
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        if tag=='a' and self.anchor:self.links.append(dict(url=self.anchor[0],label=' '.join(self.anchor[1])));self.anchor=None
        if tag in ('h1','h2','h3','title'):self.heading=max(0,self.heading-1)
        if tag in ('p','div','li','section','article','h1','h2','h3','tr','td'):self.flush()
    def handle_data(self,value):
        if self.script is not None:self.script.append(value)
        if not self.hidden:
            self.text.append(value);self.current.append(value)
            if self.heading:self.headings.append(value)
            if self.anchor:self.anchor[1].append(value)

def parse(url,body,media='text/html'):
    if 'html' not in media.lower() or len(body)>2*1024**2:raise ValueError('HTML_REQUIRED')
    p=Page();p.feed(body.decode('utf-8',errors='replace'));p.close();p.flush()
    links=[]
    for row in p.links[:5000]:
        u=public_url(urljoin(url,row['url']))
        if u:links.append(dict(url=u,label=row['label'][:250],method='html_anchor'))
    for row in extract(url,body):links.append(dict(url=row['url'],label='',method='literal_ats_reference'))
    p.links=links
    return p

def host(url):return (urlsplit(url).hostname or '').removeprefix('www.')
def same_host(a,b):return host(a)==host(b)
def same_tenant(a,b):
    x,y=identify(a),identify(b)
    if not x or not y or x['tenant_key']!=y['tenant_key']:return False
    # Only documented shared-board aliases may cross hostnames.
    return x['family'] in ('greenhouse','smartrecruiters') or urlsplit(a).hostname==urlsplit(b).hostname

def publisher_proof(employer,url,page):
    if identify(url) or not LEGAL.search(urlsplit(url).path) or not LEGAL.search(' '.join(page.headings)):return False
    return any(len(' '.join(block.split()))<=800 and matches_name(employer['company_name'],block) for block in page.blocks)

def location_supported(employer,page):
    if 'SOCIAL' not in employer.get('source_cohorts',[]):return True
    locations=employer.get('observed_locations',[])
    if not locations:return False
    content=' '+' '.join(tokens(' '.join(page.text)))+' '
    return any(len(' '.join(tokens(v)))>=4 and ' '+' '.join(tokens(v))+' ' in content for v in locations)

def posting_objects(page):
    stack=list(page.jsonld);out=[];visited=0
    while stack and visited<10000:
        v=stack.pop();visited+=1
        if isinstance(v,dict):
            kind=v.get('@type');kinds=[kind] if isinstance(kind,str) else kind
            if isinstance(kinds,list) and 'JobPosting' in kinds:out.append(v)
            stack.extend(v.values())
        elif isinstance(v,list):stack.extend(v)
    return out

def join_inventory(url,page):
    binding=identify(url)
    if not binding or binding['family']!='join':raise ValueError('JOIN_TENANT_REQUIRED')
    pattern=r'^/companies/'+re.escape(binding['tenant'])+r'/[0-9]+-[^/]+/?$'
    detail=sorted({r['url'] for r in page.links if same_tenant(url,r['url']) and re.fullmatch(pattern,urlsplit(r['url']).path)})
    text=' '.join(page.text)
    empty=bool(re.search(r'no (?:open|current) (?:positions|jobs)|keine (?:offenen|aktuellen) stellen',text,re.I))
    semantics=bool(re.search(r'open positions|offene stellen|jobs', ' '.join(page.headings),re.I))
    websites=[r['url'] for r in page.links if WEB_LABEL.fullmatch(r['label'].strip()) and not identify(r['url'])][:3]
    return dict(detail_urls=detail,explicit_empty=empty,portal_semantics=bool(semantics and (detail or empty)),website_hints=websites)

def join_detail(employer,url,page):
    result=[]
    for j in posting_objects(page):
        organization=j.get('hiringOrganization') or {}
        if not isinstance(organization,dict) or not structured_match(employer['company_name'],organization.get('name','')):continue
        if not isinstance(j.get('title'),str) or not isinstance(j.get('description'),str) or len(j['description'].strip())<40:continue
        target=public_url(j.get('url') or url)
        if not target or not same_tenant(url,target):continue
        result.append(dict(title=j['title'],description_html=j['description'],url=target,
            organization=organization.get('name'),location=j.get('jobLocation'),date_posted=j.get('datePosted'),
            employment_type=j.get('employmentType'),affinity=None,candidate_fit=None))
    return result
