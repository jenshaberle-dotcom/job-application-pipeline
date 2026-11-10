import json,unittest,base64,gzip,hashlib
from unittest.mock import patch
from src.connectors.portal_discovery.identity_contract import matches_name,structured_match
from src.connectors.portal_discovery.smartrecruiters_contract import inventory,company_matches
from src.connectors.portal_discovery.family_contracts import inventory_plan
from src.connectors.portal_discovery.field_campaign import vacancy_sample
from src.connectors.portal_discovery.resume_transport import ResumeTransport

class Repair(unittest.TestCase):
    def test_association_punctuation_with_observed_abbreviation(self):
        self.assertTrue(matches_name('Verbund Sozialtherapeutischer Einrichtungen e.V.',
            'Verbund Sozialtherapeutischer Einrichtungen e.V. (VSE)'))
        self.assertFalse(matches_name('Verbund Sozialtherapeutischer Einrichtungen e.V.',
            'Verbund Sozialtherapeutischer Einrichtungen Berlin e.V.'))
    def test_short_name_requires_entire_legal_name_block(self):
        self.assertTrue(matches_name('gGiS mbH','gGiS mbH'))
        for text in ['gGiS','gGiS GmbH','gGiS mbH Berlin','Wir arbeiten mit gGiS mbH']:
            self.assertFalse(matches_name('gGiS mbH',text))
        self.assertFalse(matches_name('GIS','GIS'))
    def test_case_only_smartrecruiters_tenant_change(self):
        p='https://careers.smartrecruiters.com/wavestone1'
        url=inventory_plan(p)['requests'][0]['url']
        data=dict(totalFound=1,content=[dict(id='42',company=dict(identifier='Wavestone1'))])
        self.assertEqual(inventory(p,url,json.dumps(data).encode())['listed'],1)
        data['content'][0]['company']['identifier']='Wavestone2'
        with self.assertRaisesRegex(ValueError,'SR_COMPANY_CONFLICT'):inventory(p,url,json.dumps(data).encode())
        for name in [None,'Wavestone1/other','Wavestone1?x=1','Wavestone1 ']:self.assertFalse(company_matches(name,'wavestone1'))
    def test_general_application_not_a_vacancy_proof(self):
        titles=['Initiativbewerbung (m/w/d)','We’re always looking for exceptional people (m/f/d)',
                'Open application','Sozialarbeiterin (m/w/d)','Application Engineer']
        jobs=[dict(title=t) for t in titles]
        self.assertEqual([x['title'] for x in vacancy_sample(jobs)],titles[-2:])
    def test_retained_success_and_failure_never_trigger_fresh_network(self):
        body=b'<h1>Saved page</h1>';sha=hashlib.sha256(body).hexdigest()
        rows=[dict(url='https://alpha.example/',sequence=7,status=200,body_sha256=sha,content_type='text/html'),
              dict(url='https://alpha.example/missing',sequence=8,status=404,content_type='text/html')]
        prior=dict(transport=dict(records=rows,bodies_gzip_base64={sha:base64.b64encode(gzip.compress(body)).decode()}))
        t=ResumeTransport(prior)
        with patch('src.connectors.portal_discovery.field_transport.resolve',side_effect=AssertionError('NO_NETWORK')):
            for row in rows:
                t.allow(row['url'],'test');receipt,_=t.read(row['url']);self.assertTrue(receipt['observation_reused'])
        self.assertEqual(t.attempts,0);self.assertEqual(t.sequence_offset,8);self.assertEqual(t.reused,2)
    def test_changed_retained_body_is_denied(self):
        prior=dict(transport=dict(records=[],bodies_gzip_base64={'0'*64:base64.b64encode(gzip.compress(b'wrong')).decode()}))
        with self.assertRaisesRegex(ValueError,'RETAINED_BODY_CHANGED'):ResumeTransport(prior)

if __name__=='__main__':unittest.main()
