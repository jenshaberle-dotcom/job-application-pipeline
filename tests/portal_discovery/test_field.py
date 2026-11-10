import hashlib,json,unittest
from urllib.parse import urlsplit
from src.connectors.portal_discovery.field_campaign import probe,campaign
from src.connectors.portal_discovery.field_html import parse,publisher_proof,join_inventory,join_detail,same_tenant
from src.connectors.portal_discovery.field_transport import target,BudgetStop
from src.connectors.portal_discovery.field_factory import CATALOG,handoff
from src.connectors.portal_discovery.family_contracts import identify,inventory_plan
from src.connectors.portal_discovery.smartrecruiters_contract import inventory,detail
from .test_candidate import fixture

E=dict(employer_id='test:alpha',company_key='alpha',company_name='Alpha GmbH',source_cohorts=['SOCIAL'],
       observed_locations=['Hannover'],hints=[dict(url='https://alpha.example/')])

class FakeTransport:
    def __init__(self,pages):self.pages=pages;self.records=[];self.allowed=set();self.stopped=False
    def allow(self,url,kind,parent=None):self.allowed.add(url);return url
    def read(self,url):
        assert url in self.allowed
        media,body=self.pages.get(url,('text/html',b''))
        row=dict(url=url,status=200 if body else 404,body_sha256=hashlib.sha256(body).hexdigest() if body else None,
                 sequence=len(self.records)+1,content_type=media)
        self.records.append(row);return row,body
    def check(self):
        if self.stopped:raise BudgetStop('TEST_BUDGET')
    def export(self):return dict(synthetic=True,requests=0,records=self.records)

def setup(family='join',location='Hannover',publisher='Alpha GmbH',delegation=None):
    if family=='join':portal='https://join.com/companies/alpha'
    elif family=='smartrecruiters':portal='https://careers.smartrecruiters.com/alpha'
    else:portal=fixture(family)[0].rstrip('/')
    joburl=portal+'/123-sozialarbeiterin'
    pages={'https://alpha.example/':('text/html',b'<h1>Alpha</h1><a href="/impressum">Impressum</a><a href="/karriere">Karriere</a>'),
           'https://alpha.example/impressum':('text/html',('<h1>Impressum</h1><p>'+publisher+'</p><p>'+location+'</p>').encode()),
           'https://alpha.example/karriere':('text/html',('<h1>Karriere</h1><a href="'+(delegation or portal)+'">Offene Positionen</a>').encode()),
           portal:('text/html',('<h1>Alpha GmbH</h1><h2>Open positions</h2><a href="'+joburl+'">Sozialarbeiterin</a>').encode())}
    if family=='join':
        data={'@type':'JobPosting','title':'Sozialarbeiterin','description':'Beratung von Familien und Jugendlichen in Hannover.','url':joburl,'hiringOrganization':{'name':'Alpha GmbH'}}
        pages[joburl]=('text/html',('<script type="application/ld+json">'+json.dumps(data)+'</script>').encode())
    elif family=='smartrecruiters':
        listurl=inventory_plan(portal)['requests'][0]['url'];detailurl='https://api.smartrecruiters.com/v1/companies/alpha/postings/42'
        pages[listurl]=('application/json',json.dumps(dict(totalFound=1,content=[dict(id='42',company=dict(identifier='alpha'))])).encode())
        pages[detailurl]=('application/json',json.dumps(dict(id='42',name='Sozialarbeiterin',active=True,
            company=dict(identifier='alpha',name='Alpha GmbH'),postingUrl='https://jobs.smartrecruiters.com/alpha/42-sozial',
            jobAd=dict(sections=dict(jobDescription=dict(text='Beratung von Familien und Jugendlichen in Hannover.'))))).encode())
    else:
        _,url,media,body=fixture(family);pages[url]=(media,body)
    return portal,pages

class Field(unittest.TestCase):
    def test_same_slug_different_personio_host_is_not_authority_alias(self):
        self.assertFalse(same_tenant('https://alpha.jobs.personio.de/','https://alpha.jobs.personio.com/'))
        self.assertTrue(same_tenant('https://boards.greenhouse.io/alpha','https://job-boards.greenhouse.io/alpha'))
    def test_alternative_observed_legal_link_is_tried_after_unavailable_link(self):
        portal,pages=setup()
        pages['https://alpha.example/']=('text/html',b'<h1>Alpha</h1><a href="/impressum-old">Impressum</a><a href="/impressum">Impressum</a><a href="/karriere">Karriere</a>')
        r=probe(E,dict(url=portal,origins=['test']),FakeTransport(pages))
        self.assertEqual(r['status'],'INDEPENDENT_PORTAL_EVIDENCE_CANDIDATE')
    def test_alternative_observed_career_link_is_tried(self):
        portal,pages=setup()
        pages['https://alpha.example/']=('text/html',b'<h1>Alpha</h1><a href="/impressum">Impressum</a><a href="/jobs-old">Jobs</a><a href="/karriere">Karriere</a>')
        r=probe(E,dict(url=portal,origins=['test']),FakeTransport(pages))
        self.assertEqual(r['status'],'INDEPENDENT_PORTAL_EVIDENCE_CANDIDATE')
    def test_full_chain_all_five_families_with_independent_publisher(self):
        for family in ('join','personio','greenhouse','dvinci','smartrecruiters'):
            with self.subTest(family=family):
                portal,pages=setup(family);r=probe(E,dict(url=portal,origins=['test']),FakeTransport(pages))
                self.assertEqual(r['status'],'INDEPENDENT_PORTAL_EVIDENCE_CANDIDATE',r)
                self.assertTrue(r['sample_job_proof']);self.assertFalse(r['production_admitted'])
                self.assertEqual(r['factory']['status'],'LIVE_CONTENT_FACTORY_CANDIDATE')
                self.assertTrue(all(j['affinity'] is None for j in r['jobs']))
    def test_same_name_wrong_social_location_is_not_authority(self):
        portal,pages=setup(location='Zuerich Schweiz')
        r=probe(E,dict(url=portal,origins=['test']),FakeTransport(pages))
        self.assertEqual(r['status'],'UNVERIFIED');self.assertIsNone(r['authority'])
        self.assertIn('SOCIAL_LOCATION_UNPROVEN_OR_CONFLICTING',r['authority_gaps'])
    def test_other_publisher_not_verified(self):
        portal,pages=setup(publisher='Alpha Energy GmbH')
        self.assertIsNone(probe(E,dict(url=portal,origins=['test']),FakeTransport(pages))['authority'])
    def test_exact_name_on_ats_alone_does_not_count(self):
        portal,pages=setup();employer=dict(E,hints=[])
        r=probe(employer,dict(url=portal,origins=['directory']),FakeTransport(pages))
        self.assertFalse(r.get('sample_job_proof'));self.assertEqual(r['status'],'UNVERIFIED')
    def test_different_tenant_on_same_shared_host_denied(self):
        portal,pages=setup(delegation='https://join.com/companies/alpha-energy')
        self.assertIsNone(probe(E,dict(url=portal,origins=['test']),FakeTransport(pages))['authority'])
        self.assertFalse(same_tenant('https://boards.greenhouse.io/alpha','https://boards.greenhouse.io/other'))
    def test_partial_stop_never_repeats_previous_outcomes(self):
        t=FakeTransport({});t.stopped=True
        plan=dict(enrolled=[dict(employer=E,candidates=[]),dict(employer=dict(E,employer_id='next'),candidates=[])],selection={})
        r=campaign(plan,t)
        self.assertEqual(r['outcomes'][0]['outcomes'],[]);self.assertEqual(r['unattempted_due_to_budget'],['next'])
        self.assertFalse(r['summary']['target_90_met'])
    def test_join_empty_is_not_job_proof(self):
        portal,pages=setup();pages[portal]=('text/html',b'<h1>Jobs</h1><p>No open positions</p>')
        r=probe(E,dict(url=portal,origins=['test']),FakeTransport(pages))
        self.assertEqual(r['status'],'INDEPENDENT_PORTAL_EVIDENCE_CANDIDATE');self.assertFalse(r['sample_job_proof'])
    def test_join_job_wrong_hiring_organization_hidden(self):
        p=parse('https://join.com/companies/alpha/123-job',b'<script type="application/ld+json">{"@type":"JobPosting","title":"Job","description":"A very long job description to exceed forty characters.","hiringOrganization":{"name":"Other GmbH"}}</script>')
        self.assertEqual(join_detail(E,'https://join.com/companies/alpha/123-job',p),[])
    def test_smartrecruiters_internal_and_wrong_company_not_accepted(self):
        portal,pages=setup('smartrecruiters');u=inventory_plan(portal)['requests'][0]['url']
        self.assertIn('destination=PUBLIC',u)
        with self.assertRaisesRegex(ValueError,'CONFLICT'):inventory(portal,u,b'{"totalFound":1,"content":[{"id":"42","company":{"identifier":"other"}}]}')
    def test_smartrecruiters_pagination_not_hidden(self):
        p,_=setup('smartrecruiters');u=inventory_plan(p)['requests'][0]['url']
        r=inventory(p,u,b'{"totalFound":2,"content":[{"id":"42","company":{"identifier":"alpha"}}]}')
        self.assertFalse(r['inventory_complete'])
    def test_transport_denies_ip_provider_auth_and_secrets(self):
        for u in ('https://127.0.0.1/','https://api.openai.com/v1','https://alpha.example/login','https://alpha.example/?access_token=abc'):
            with self.subTest(u=u),self.assertRaises(ValueError):target(u)
    def test_factory_preserves_existing_capabilities(self):
        from src.connectors.portal_discovery.factory_candidate import CATALOG as old
        self.assertEqual(CATALOG[:len(old)],old);self.assertEqual(len(CATALOG),9)
    def test_no_factory_without_authority(self):
        self.assertEqual(handoff(E,'https://join.com/companies/alpha','join',[{'title':'x'}],None,['h'])['status'],'AUTHORITY_AND_NONEMPTY_JOB_PROOF_REQUIRED')

if __name__=='__main__':unittest.main()
