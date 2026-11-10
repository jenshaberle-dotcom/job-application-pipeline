"""Complete candidate chain: public page -> independent publisher -> feed/detail -> factory.

This does not dispatch RCC consumers or register recipes. Every result remains a
reviewable source-evidence candidate, and untouched corpus records remain visible.
"""
import hashlib,json,time,re
from collections import Counter
from urllib.parse import urlsplit,urlunsplit
from .family_contracts import identify,inventory_plan,public_url
from .ats_payloads import parse_inventory
from .field_html import (parse,LEGAL,CAREER,WEB_LABEL,same_host,same_tenant,publisher_proof,
                        location_supported,join_inventory,join_detail)
from .field_transport import BudgetStop,Transport,target
from .field_factory import handoff
from .smartrecruiters_contract import inventory as sr_inventory,detail as sr_detail

SUPPORTED={'join','personio','greenhouse','dvinci','smartrecruiters'}
GENERAL_APPLICATION=re.compile(r'initiativbewerbung|unsolicited application|open application|general application|talent (?:pool|community)|always looking for exceptional people',re.I)

def vacancy_sample(jobs):
    """Do not count an evergreen application invitation as an advertised position."""
    return [j for j in jobs if not GENERAL_APPLICATION.search(j.get('title',''))]
INTERMEDIARIES=('join.com','arbeitsagentur.de','linkedin.com','facebook.com','stepstone.de','indeed.com',
               'xing.com','northdata.de','companyhouse.de','kununu.com','firmenwissen.de','wikipedia.org')

def is_origin(url):
    p=urlsplit(url);h=(p.hostname or '').removeprefix('www.')
    return bool(public_url(url) and not identify(url) and not any(h==x or h.endswith('.'+x) for x in INTERMEDIARIES))

class Case:
    def __init__(self,employer,t):self.employer=employer;self.t=t;self.reads=0;self.steps=[]
    def read(self,url,kind,parent=None):
        if self.reads>=20:raise ValueError('CASE_READ_BUDGET')
        self.reads+=1;u=self.t.allow(url,kind,parent);r,b=self.t.read(u)
        self.steps.append(dict(url=u,receipt=r['sequence'],status=r['status'],kind=kind,error=r.get('error')))
        if r['status']!=200 or not r.get('body_sha256'):raise ValueError('PUBLIC_READ_UNAVAILABLE')
        return r,b
    def html(self,url,kind,parent=None):
        r,b=self.read(url,kind,parent);return r,parse(r['url'],b,r['content_type'])
    def authority(self,portal,page,portal_receipt):
        seeds=[]
        for hint in self.employer.get('hints',[]):
            u=hint.get('url','')
            if is_origin(u):seeds.append((u,'retained_metadata',None))
        if page:
            for link in page.links:
                if is_origin(link['url']) and (WEB_LABEL.fullmatch(link['label'].strip()) or LEGAL.search(link['label'])):
                    seeds.append((link['url'],'observed_ats_website_or_legal_link',portal_receipt['sequence']))
        unique={}
        for seed in seeds:
            h=urlsplit(seed[0]).hostname
            if h not in unique or len(seed[0])<len(unique[h][0]):unique[h]=seed
        failures=[]
        for start,kind,parent in list(unique.values())[:3]:
            try:
                root,page1=self.html(start,kind,parent)
                if not is_origin(root['url']):continue
                pages=[(root,page1)]
                legal=[l['url'] for l in page1.links if same_host(root['url'],l['url']) and LEGAL.search(l['label']+' '+urlsplit(l['url']).path)][:2]
                proof=None
                if publisher_proof(self.employer,root['url'],page1):proof=(root,page1)
                for url in legal:
                    if proof:break
                    try:
                        lr,lp=self.html(url,'observed_imprint_link',root['sequence'])
                        if same_host(root['url'],lr['url']) and publisher_proof(self.employer,lr['url'],lp):proof=(lr,lp);pages.append((lr,lp))
                    except BudgetStop:raise
                    except Exception:failures.append('OBSERVED_IMPRINT_LINK_UNAVAILABLE')
                if not proof:failures.append('PUBLISHER_NOT_PROVEN');continue
                # For SOCIAL, location evidence must be on the independently identified publisher site.
                if not any(location_supported(self.employer,p) for _,p in pages):
                    failures.append('SOCIAL_LOCATION_UNPROVEN_OR_CONFLICTING');continue
                def delegation():
                    for receipt,p in pages:
                        for link in p.links:
                            if same_tenant(portal,link['url']):return dict(kind='PUBLISHER_OBSERVED_ATS_DELEGATION',
                                publisher_url=proof[0]['url'],publisher_sha256=proof[0]['body_sha256'],
                                link_page=receipt['url'],link_page_sha256=receipt['body_sha256'],observed_link=link['url'],
                                tenant_key=identify(portal)['tenant_key'],location_check='MATCHED' if 'SOCIAL' in self.employer.get('source_cohorts',[]) else 'NOT_REQUIRED',
                                evidence_scope='UNPRIVILEGED_PUBLIC_READ_NOT_RCC_ROOT_ADMISSION')
                    return None
                found=delegation()
                if found:return found,failures
                follow=[l['url'] for l in page1.links if same_host(root['url'],l['url']) and CAREER.search(l['label']+' '+urlsplit(l['url']).path)]
                for url in list(dict.fromkeys(follow))[:2]:
                    try:
                        cr,cp=self.html(url,'observed_official_career_link',root['sequence'])
                        if not same_host(root['url'],cr['url']):continue
                        pages.append((cr,cp));found=delegation()
                        if found:return found,failures
                    except BudgetStop:raise
                    except Exception:failures.append('OBSERVED_CAREER_LINK_UNAVAILABLE')
                failures.append('OFFICIAL_ATS_LINK_NOT_FOUND')
            except BudgetStop:raise
            except Exception as e:failures.append(str(e)[:120] if isinstance(e,ValueError) else type(e).__name__)
        return None,failures or ['NO_INDEPENDENT_PUBLISHER_SEED']

def probe(employer,candidate,t):
    c=Case(employer,t);portal=candidate['url'];binding=identify(portal);family=binding['family'];page=None;r=None
    out=dict(url=portal,family=family,origins=candidate['origins'],authority=None,portal_content=False,
        status='UNVERIFIED',jobs=[],factory=None,production_admitted=False)
    try:
        try:
            r,page=c.html(portal,'frozen_candidate')
            if not same_tenant(portal,r['url']):raise ValueError('REDIRECT_TENANT_CHANGED')
        except BudgetStop:raise
        except Exception as e:
            page=None;out['html_error']=str(e)[:120]
        authority,failures=c.authority(portal,page,r)
        out['authority']=authority;out['authority_gaps']=failures
        jobs=[];source_hashes=[];inventory_info={}
        if family=='join':
            if page is None:raise ValueError('JOIN_HTML_MISSING')
            inventory_info=join_inventory(portal,page);out['portal_content']=inventory_info['portal_semantics']
            if authority:
                for url in inventory_info['detail_urls'][:2]:
                    dr,dp=c.html(url,'observed_join_detail',r['sequence'])
                    if same_tenant(portal,dr['url']):jobs.extend(join_detail(employer,dr['url'],dp));source_hashes.append(dr['body_sha256'])
        else:
            plan=inventory_plan(portal)
            if not plan['requests']:raise ValueError(plan['status'])
            fr,fb=c.read(plan['requests'][0]['url'],'documented_public_family_endpoint',r['sequence'] if r else None)
            source_hashes.append(fr['body_sha256'])
            if family=='smartrecruiters':
                if 'json' not in fr['content_type']:raise ValueError('SR_JSON_REQUIRED')
                inventory_info=sr_inventory(portal,fr['url'],fb);out['portal_content']=True
                if authority:
                    for url in inventory_info['detail_urls'][:2]:
                        dr,db=c.read(url,'documented_detail_from_observed_id',fr['sequence'])
                        if 'json' not in dr['content_type']:raise ValueError('SR_JSON_REQUIRED')
                        jobs.append(sr_detail(portal,dr['url'],db));source_hashes.append(dr['body_sha256'])
            else:
                inventory_info=parse_inventory(portal,fr['url'],fr['content_type'],fb);out['portal_content']=True
                jobs=[j for j in inventory_info['jobs'] if j['details_complete'] and not j['external_detail_requires_validation'] and same_tenant(portal,j['url'])][:2] if authority else []
        out['inventory']={k:v for k,v in inventory_info.items() if k not in ('jobs','detail_urls')}
        out['observed_detail_count']=len(inventory_info.get('detail_urls',[]))
        out['jobs']=jobs
        vacancies=vacancy_sample(jobs)
        out['sample_vacancies']=len(vacancies)
        out['general_application_listings']=len(jobs)-len(vacancies)
        out['factory']=handoff(employer,portal,family,vacancies,authority,source_hashes)
        out['status']='INDEPENDENT_PORTAL_EVIDENCE_CANDIDATE' if authority and out['portal_content'] else 'UNVERIFIED'
        out['sample_job_proof']=bool(authority and vacancies)
    except BudgetStop:raise
    except Exception as e:
        out['error']=dict(type=type(e).__name__,code=str(e)[:200] if isinstance(e,ValueError) else 'SOURCE_OR_PARSE_FAILED')
    out['steps']=c.steps
    return out

def campaign(plan,t=None):
    t=t or Transport();rows=[];halt=None
    for index,entry in enumerate(plan['enrolled']):
        outcomes=[]
        try:
            t.check()
            for candidate in entry['candidates']:outcomes.append(probe(entry['employer'],candidate,t))
            rows.append(dict(employer_id=entry['employer']['employer_id'],outcomes=outcomes,status='EXAMINED'))
        except BudgetStop as e:
            # Keep partial observations; never equate budget exhaustion with no portal.
            rows.append(dict(employer_id=entry['employer']['employer_id'],outcomes=outcomes,status='BUDGET_INTERRUPTED'))
            halt=str(e);break
    inspected={r['employer_id'] for r in rows}
    untouched=[e['employer']['employer_id'] for e in plan['enrolled'] if e['employer']['employer_id'] not in inspected]
    all_outcomes=[o for r in rows for o in r['outcomes']]
    proven={r['employer_id'] for r in rows if any(o['status']=='INDEPENDENT_PORTAL_EVIDENCE_CANDIDATE' for o in r['outcomes'])}
    jobproof={r['employer_id'] for r in rows if any(o.get('sample_job_proof') for o in r['outcomes'])}
    return dict(version='0.12.20',status='PUBLIC_FIELD_EVIDENCE_COMPLETE_NOT_ADMITTED' if not halt else 'PUBLIC_FIELD_BUDGET_STOP_PARTIAL_PRESERVED',
        phase='COMPLETE' if not halt else 'BUDGET_STOP',stop_reason=halt,automatic_retry=False,
        summary=dict(frozen_denominator=3380,enrolled_records=len(plan['enrolled']),started_records=len(rows),examined_records=sum(r['status']=='EXAMINED' for r in rows),
            unattempted_budget_records=len(untouched),outside_selected_family_records=3380-len(plan['enrolled']),
            independent_portal_evidence_candidates=len(proven),records_with_sample_job_proof=len(jobproof),
            factory_candidates=sum(o.get('factory',{}).get('status')=='LIVE_CONTENT_FACTORY_CANDIDATE' for o in all_outcomes if o.get('factory')),
            by_status=dict(Counter(o['status'] for o in all_outcomes)),target_90_met=False,autonomous_success_rate=None),
        outcomes=rows,unattempted_due_to_budget=untouched,transport=t.export(),selection=plan['selection'],
        production_activation=False,consumer_dispatches=0,database_writes=0,service_changes=0,gui_changes=0,
        credential_access=False,windows_full_access_enabled=False,linux_writes=0,live_provider_calls=0,
        evidence_scope='UNPRIVILEGED_OPERATOR_PUBLIC_READ_NOT_RCC_DISPATCH',
        independent_root_admission_required=True,user_acceptance='PENDING',jap_daily_e2e_passed=False,
        next_gate='REVIEW_INDEPENDENT_SOURCE_PROOFS_AND_FACTORY_GAPS_BEFORE_RCC_ADMISSION')
