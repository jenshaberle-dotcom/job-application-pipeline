"""Bounded public inventory parsers; content evidence is separate from authority."""
import hashlib
import json
import re
from xml.etree import ElementTree as ET
from .family_contracts import identify, inventory_plan, public_url

MAX_BYTES = 8 * 1024**2
MAX_JOBS = 10000

def need(ok, code):
    if not ok:raise ValueError(code)

def text(value, limit=262144):
    return value if isinstance(value,str) and len(value)<=limit else ''

def make_job(jid, title, url, description, location=None, organization=None, extra=None):
    need(isinstance(jid,(int,str)) and not isinstance(jid,bool) and re.fullmatch(r'[a-zA-Z0-9_-]{1,128}',str(jid)), 'JOB_ID')
    need(bool(text(title,2000).strip()) and public_url(url), 'JOB_TITLE_URL')
    return dict(id=str(jid),title=title,url=url,description_html=text(description),
        details_complete=bool(text(description).strip()),location=location,
        organization=organization,attributes=extra or {},candidate_fit=None,affinity=None,
        employer_binding_verified=False,product_admitted=False)

def parse_personio(body, binding):
    decoded=body.decode('utf-8-sig',errors='strict')
    need(not re.search(r'<!\s*(?:DOCTYPE|ENTITY)',decoded,re.I), 'XML_DTD_OR_ENTITY_DENIED')
    root=ET.fromstring(decoded)
    need(root.tag=='workzag-jobs','PERSONIO_ROOT')
    nodes=list(root)
    need(len(nodes)<=MAX_JOBS and all(n.tag=='position' for n in nodes),'PERSONIO_ROWS')
    result=[]
    for node in nodes:
        get=lambda k:node.findtext(k) or ''
        blocks=[]
        for block in node.findall('jobDescriptions/jobDescription'):
            # Descriptions remain untrusted HTML. Do not execute/render here.
            blocks.append(block.findtext('value') or '')
        result.append(make_job(get('id'),get('name'),binding['portal_url']+'/job/'+get('id'),
            '\n'.join(blocks),get('office'),get('subcompany'),
            {k:get(k) for k in ('employmentType','schedule','department','seniority','createdAt')}))
    return result, True

def parse_greenhouse(body, binding):
    data=json.loads(body)
    need(isinstance(data,dict) and isinstance(data.get('jobs'),list),'GREENHOUSE_SCHEMA')
    need(len(data['jobs'])<=MAX_JOBS,'JOB_COUNT')
    total=data.get('meta',{}).get('total')
    need(total is None or type(total) is int and total>=0,'GREENHOUSE_TOTAL')
    result=[]
    for job in data['jobs']:
        need(isinstance(job,dict),'JOB_ROW')
        location=job.get('location')
        result.append(make_job(job.get('id'),job.get('title'),job.get('absolute_url'),job.get('content'),
            location.get('name') if isinstance(location,dict) else None,job.get('company_name'),
            {k:job.get(k) for k in ('updated_at','departments','offices','metadata')}))
    return result, total is None or total==len(result)

def parse_dvinci(body, binding):
    data=json.loads(body)
    need(isinstance(data,list) and len(data)<=MAX_JOBS,'DVINCI_SCHEMA')
    result=[]
    for job in data:
        need(isinstance(job,dict),'JOB_ROW')
        opening=job.get('jobOpening') or {}
        need(isinstance(opening,dict),'DVINCI_OPENING')
        if opening.get('type')=='UNSOLICITED':
            continue
        content=job.get('renderedContent') or {}; pieces=[]
        need(isinstance(content,dict),'DVINCI_CONTENT')
        for field in ('introduction','tasks','profile','weOffer','additionalInformation','closingText'):
            part=content.get(field)
            val=part.get('body') if isinstance(part,dict) else job.get(field)
            if isinstance(val,str):pieces.append(val)
        company=opening.get('company')
        result.append(make_job(job.get('id'),job.get('position'),job.get('jobPublicationURL'),
            '\n'.join(pieces),opening.get('locations'),
            company.get('name') if isinstance(company,dict) else None,
            {k:opening.get(k) for k in ('workingTimes','contractPeriod','categories')}))
    return result, True

PARSERS={'personio':parse_personio,'greenhouse':parse_greenhouse,'dvinci':parse_dvinci}

def parse_inventory(observed_portal, response_url, content_type, body):
    need(isinstance(body,bytes) and len(body)<=MAX_BYTES,'FEED_BYTE_BUDGET')
    plan=inventory_plan(observed_portal); binding=plan.get('binding')
    need(binding and binding['family'] in PARSERS and plan['requests'],'FEED_FAMILY_OR_SUBSCOPE')
    need(response_url==plan['requests'][0]['url'],'FEED_ENDPOINT_BINDING')
    media=content_type.split(';')[0].strip().lower()
    if binding['family']=='personio':need(media in ('application/xml','text/xml'),'FEED_MEDIA_TYPE')
    else:need(media in ('application/json','text/json'),'FEED_MEDIA_TYPE')
    jobs,complete=PARSERS[binding['family']](body,binding)
    need(len({j['id'] for j in jobs})==len(jobs),'DUPLICATE_JOB_IDS')
    # An external detail link needs its own authority proof, not tenant inheritance.
    for job in jobs:
        child=identify(job['url'])
        job['detail_same_tenant']=bool(child and child['tenant_key']==binding['tenant_key'])
        job['external_detail_requires_validation']=not job['detail_same_tenant']
    return dict(status='ATS_CONTENT_PARSED_EMPLOYER_AUTHORITY_REQUIRED',family=binding['family'],
        binding=binding,inventory_complete=complete,explicit_empty=complete and not jobs,
        job_count=len(jobs),jobs=jobs,body_sha256=hashlib.sha256(body).hexdigest(),
        response_url=response_url,fingerprint_tags=['observed_'+binding['family']+'_inventory'],
        portal_verified=False,live_job_proof=False,production_admitted=False)
