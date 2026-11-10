import json,re
from .family_contracts import identify,inventory_plan,public_url

def company_matches(observed,expected):
    # identify() already canonicalizes board tenant paths to lower case. The
    # authenticated public API retains spelling such as Wavestone1/Continental.
    return (isinstance(observed,str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{1,128}',observed))
            and observed.casefold()==expected.casefold())

def inventory(portal,response_url,body):
    binding=identify(portal);plan=inventory_plan(portal)
    if not binding or binding['family']!='smartrecruiters' or response_url!=plan['requests'][0]['url']:raise ValueError('SR_LIST_BINDING')
    data=json.loads(body)
    if not isinstance(data,dict) or not isinstance(data.get('content'),list) or len(data['content'])>100:raise ValueError('SR_LIST_SCHEMA')
    total=data.get('totalFound')
    if type(total) is not int or total<0:raise ValueError('SR_TOTAL')
    urls=[]
    for row in data['content']:
        company=row.get('company',{})
        if not company_matches(company.get('identifier'),binding['tenant']):raise ValueError('SR_COMPANY_CONFLICT')
        ident=row.get('id') or row.get('uuid')
        if not isinstance(ident,str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,128}',ident):raise ValueError('SR_POSTING_ID')
        # Ignore arbitrary ref URLs. Derive the documented endpoint from the verified list ID.
        urls.append('https://api.smartrecruiters.com/v1/companies/'+binding['tenant']+'/postings/'+ident)
    return dict(detail_urls=urls,total=total,listed=len(data['content']),inventory_complete=total==len(data['content']),explicit_empty=total==0)

def detail(portal,url,body):
    binding=identify(portal);root='https://api.smartrecruiters.com/v1/companies/'+binding['tenant']+'/postings/'
    if not url.startswith(root) or '/' in url[len(root):] or '?' in url:raise ValueError('SR_DETAIL_BINDING')
    j=json.loads(body)
    if not company_matches(j.get('company',{}).get('identifier'),binding['tenant']) or j.get('active') is not True:raise ValueError('SR_DETAIL_COMPANY_OR_INACTIVE')
    if url[len(root):] not in (j.get('id'),j.get('uuid')):raise ValueError('SR_DETAIL_ID')
    target=public_url(j.get('postingUrl'));b=identify(target)
    if not b or b['tenant_key']!=binding['tenant_key']:raise ValueError('SR_JOB_URL')
    sections=j.get('jobAd',{}).get('sections',{})
    body='\n'.join(sections.get(k,{}).get('text','') for k in ('jobDescription','qualifications','additionalInformation'))
    if not isinstance(j.get('name'),str) or len(body.strip())<40:raise ValueError('SR_DETAIL_INCOMPLETE')
    return dict(title=j['name'],description_html=body,url=target,organization=j['company'].get('name'),
        location=j.get('location'),affinity=None,candidate_fit=None)
