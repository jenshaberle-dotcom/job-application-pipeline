import csv
import io
import json
import unittest
from src.connectors.portal_discovery.family_contracts import identify, inventory_plan, public_url
from src.connectors.portal_discovery.discovery_candidate import extract, navigation_links
from src.connectors.portal_discovery.directory_match import parse_directory, reconcile
from src.connectors.portal_discovery.ats_payloads import parse_inventory
from src.connectors.portal_discovery.factory_candidate import qualify_content

E={'employer_id':'fixture:1','company_key':'alpha','company_name':'Alpha GmbH','hints':[],'source_cohorts':['SOCIAL']}

def directory(rows):
    out=io.StringIO(newline=''); w=csv.writer(out); w.writerow(['ats','name','slug','url']); w.writerows(rows)
    return out.getvalue().encode('utf-8')

def fixture(family):
    if family=='personio':
        portal='https://alpha.jobs.personio.de/'
        body='''<workzag-jobs><position><id>42</id><name>Sozialarbeiterin</name><office>Hannover</office><subcompany>Alpha GmbH</subcompany><schedule>part-time</schedule><jobDescriptions><jobDescription><name>Aufgaben</name><value>&lt;p&gt;Beratung von Familien&lt;/p&gt;</value></jobDescription></jobDescriptions></position></workzag-jobs>'''.encode()
        media='application/xml'
    elif family=='greenhouse':
        portal='https://boards.greenhouse.io/alpha'
        body=json.dumps({'jobs':[{'id':42,'title':'Sozialarbeiterin','absolute_url':portal+'/jobs/42',
            'content':'<p>Beratung von Familien</p>','location':{'name':'Hannover'}}], 'meta':{'total':1}}).encode()
        media='application/json'
    else:
        portal='https://alpha.dvinci-hr.com/'
        body=json.dumps([{'id':42,'position':'Sozialarbeiterin','jobPublicationURL':portal+'de/jobs/42',
            'jobOpening':{'type':'DEFAULT','company':{'name':'Alpha GmbH'}},
            'renderedContent':{'tasks':{'body':'<p>Beratung von Familien</p>'}}}]).encode()
        media='application/json'
    return portal,inventory_plan(portal)['requests'][0]['url'],media,body

class Families(unittest.TestCase):
    def test_explicit_personio_com_and_de(self):
        for suffix in ('de','com'):
            p=inventory_plan('https://alpha.jobs.personio.'+suffix+'/job/12')
            self.assertEqual(p['binding']['tenant'],'alpha')
            self.assertEqual(len(p['requests']),1)
    def test_spoofed_or_private_urls_not_recognized(self):
        for u in ('https://127.0.0.1/','https://alpha.jobs.personio.de.evil.example/',
                  'https://user@alpha.jobs.personio.de/','https://alpha.jobs.personio.de/%0d',
                  'https://certificate.softgarden.io/','https://alpha.jobs.personio.de:444/'):
            self.assertIsNone(identify(u))
    def test_dvinci_custom_scope_preserved(self):
        p=inventory_plan('https://alpha.dvinci-hr.com/portal/Brand/jobs/12')
        self.assertIn('/portal/Brand/jobPublication/',p['requests'][0]['url'])
        self.assertFalse(inventory_plan('https://alpha.dvinci-hr.com/de/p/Brand/jobs/12')['requests'])
    def test_softgarden_never_assumes_api_credentials(self):
        p=inventory_plan('https://alpha.softgarden.io/job/42')
        self.assertEqual(p['binding']['family'],'softgarden');self.assertEqual(p['requests'],[])
        self.assertFalse(p['credentials_required'])
    def test_greenhouse_opaque_label_is_kept(self):
        rows=navigation_links('https://alpha.example/',[{'url':'https://boards.greenhouse.io/alpha','label':'Offene Positionen'}])
        self.assertEqual(len(rows),1);self.assertFalse(rows[0]['authority_verified'])
    def test_js_literals_and_iframe_are_hints_not_authority(self):
        rows=extract('https://alpha.example/',b'<script>var x="https:\\/\\/boards.greenhouse.io/alpha";</script><iframe src="https://alpha.jobs.personio.de/"></iframe>')
        self.assertEqual(len(rows),2);self.assertTrue(all(not r['portal_verified'] for r in rows))
    def test_no_js_execution_or_interpolated_tenant(self):
        rows=extract('https://alpha.example/',b'<script>fetch("https://example.com/x"); var x=`https://${secret}.jobs.personio.de/`;</script>')
        self.assertEqual(rows,[])

class Directory(unittest.TestCase):
    def test_legacy_slug_and_duplicate_lineage(self):
        rows,summary=parse_directory(directory([['personio','Alpha GmbH','','alpha'],['personio','Alpha GmbH','','alpha']]))
        self.assertEqual(summary['raw_rows'],2);self.assertEqual(summary['duplicates'],1)
        self.assertEqual(rows[0]['conversion'],'DOCUMENTED_LEGACY_SLUG_DERIVATION')
    def test_unknown_slug_is_held(self):
        rows,summary=parse_directory(directory([['unknown','Alpha GmbH','','alpha']]))
        self.assertEqual(rows,[]);self.assertEqual(summary['held_rows'],1)
    def test_source_family_conflict_held(self):
        rows,s=parse_directory(directory([['personio','Alpha GmbH','','https://boards.greenhouse.io/alpha']]))
        self.assertFalse(rows);self.assertEqual(s['held'][0]['reason'],'ATS_FAMILY_URL_CONFLICT')
    def test_all_records_kept_and_scores_never_verified(self):
        rows,s=parse_directory(directory([['personio','Alpha GmbH','','alpha']]))
        r=reconcile([E,dict(E,employer_id='fixture:2',company_name='Beta GmbH',source_cohorts=['TECH'])],rows,s['directory_sha256'])
        self.assertEqual(r['denominator'],2);self.assertEqual(len(r['records']),2)
        self.assertEqual(r['verified_new_portals'],0);self.assertFalse(r['target_90_met'])
        self.assertEqual(r['records'][0]['candidates'][0]['origin'],'external_ats_directory')
    def test_siemens_energy_not_merged_with_siemens(self):
        rows,s=parse_directory(directory([['personio','Siemens Energy AG','','siemensenergy']]))
        r=reconcile([dict(E,company_name='Siemens AG')],rows,s['directory_sha256'])
        self.assertEqual(r['records'][0]['status'],'NO_DIRECTORY_MATCH')
    def test_conflicting_legal_form_not_exact(self):
        rows,s=parse_directory(directory([['personio','Alpha AG','','alpha']]))
        r=reconcile([E],rows,s['directory_sha256'])
        self.assertEqual(r['records'][0]['status'],'REVIEW_ONLY')
    def test_multiple_targets_not_silently_picked(self):
        rows,s=parse_directory(directory([['personio','Alpha GmbH','','alpha'],['greenhouse','Alpha GmbH','','alpha']]))
        r=reconcile([E],rows,s['directory_sha256'])
        self.assertEqual(r['records'][0]['status'],'MULTIPLE_CANDIDATES_UNVERIFIED')
    def test_bad_rows_cannot_be_treated_as_empty_directory(self):
        with self.assertRaises(ValueError):parse_directory(b'name,url\nAlpha,https://alpha.example/\n')
        with self.assertRaises(ValueError):reconcile([E,E],[],'0'*64)

class Payloads(unittest.TestCase):
    def test_existing_html_capabilities_preserved(self):
        from src.connectors.portal_discovery.factory_candidate import CATALOG
        from src.connectors.portal_discovery.factory_catalog_baseline import CATALOG as ORIGINAL
        self.assertEqual(CATALOG[:len(ORIGINAL)],ORIGINAL)
        self.assertEqual(len(CATALOG),len(ORIGINAL)+3)
    def test_three_families_execute_parsers_and_existing_compiler(self):
        for family in ('personio','greenhouse','dvinci'):
            with self.subTest(family=family):
                r=qualify_content(E,*fixture(family))
                self.assertTrue(r['definition_qualified']);self.assertFalse(r['live_job_proof'])
                self.assertEqual(r['parsed']['job_count'],1)
                self.assertIn('Beratung',r['parsed']['jobs'][0]['description_html'])
                self.assertIsNone(r['parsed']['jobs'][0]['affinity'])
                self.assertEqual(len(r['recipe']['bindings']),2)
    def test_xml_entity_denied(self):
        p,u,m,_=fixture('personio')
        with self.assertRaisesRegex(ValueError,'DTD'):parse_inventory(p,u,m,b'<!DOCTYPE x [<!ENTITY z SYSTEM "file:///etc/passwd">]><workzag-jobs/>')
    def test_cross_tenant_response_and_wrong_media_denied(self):
        p,u,m,b=fixture('personio')
        with self.assertRaisesRegex(ValueError,'BINDING'):parse_inventory(p,u.replace('alpha','beta'),m,b)
        with self.assertRaisesRegex(ValueError,'MEDIA'):parse_inventory(p,u,'text/html',b)
    def test_partial_greenhouse_inventory_is_not_qualified(self):
        p,u,m,b=fixture('greenhouse');d=json.loads(b);d['meta']['total']=5
        r=qualify_content(E,p,u,m,json.dumps(d).encode())
        self.assertFalse(r['definition_qualified'])
    def test_detail_content_missing_is_not_full_job_proof(self):
        p,u,m,b=fixture('greenhouse');d=json.loads(b);d['jobs'][0].pop('content')
        self.assertFalse(qualify_content(E,p,u,m,json.dumps(d).encode())['definition_qualified'])
    def test_valid_empty_distinct_from_error_payload(self):
        p,u,m,_=fixture('greenhouse')
        r=parse_inventory(p,u,m,b'{"jobs":[],"meta":{"total":0}}');self.assertTrue(r['explicit_empty'])
        with self.assertRaises(ValueError):parse_inventory(p,u,m,b'{"error":"blocked"}')
    def test_duplicate_id_denied(self):
        p,u,m,b=fixture('greenhouse');d=json.loads(b);d['jobs']*=2
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):parse_inventory(p,u,m,json.dumps(d).encode())
    def test_foreign_detail_requires_independent_validation(self):
        p,u,m,b=fixture('greenhouse');d=json.loads(b);d['jobs'][0]['absolute_url']='https://other.example/jobs/1'
        r=parse_inventory(p,u,m,json.dumps(d).encode())
        self.assertTrue(r['jobs'][0]['external_detail_requires_validation']);self.assertFalse(r['portal_verified'])

def qualification():
    result=unittest.TestResult();unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__)).run(result)
    if not result.wasSuccessful():
        raise ValueError('LOCAL_CONTRACT_TESTS_FAILED:'+str([(str(t),e[-500:]) for t,e in result.errors+result.failures]))
    return dict(status='OFFLINE_CANDIDATE_CONTRACTS_PASSED',tests=result.testsRun,
                synthetic_fixtures=True,live_execution_qualified=False,production_admitted=False)

if __name__=='__main__':
    unittest.main()
