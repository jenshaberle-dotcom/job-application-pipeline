from types import SimpleNamespace
import pytest
from src.connectors import generic_employer_origin_search as search
from src.connectors import generic_employer_origin_product as product
from src.connectors.employer_origin_acquisition import AcquiredJobPage
from src import run_silver_jobs as silver


def test_inventory_does_not_apply_title_query_or_hidden_location(monkeypatch):
    seen=[]
    monkeypatch.setattr(search, 'search_workday', lambda **kw: None)
    monkeypatch.setattr(search, 'search_form_surface', lambda **kw: pytest.fail('personal form used'))
    monkeypatch.setattr(search, '_detail_candidates', lambda *a,**k:[('https://acme.test/job/1','anchor',True)])
    job=AcquiredJobPage('https://acme.test/job/1','https://acme.test/job/1',200,
        'Nurse Sydney',2000,'jsonld_jobposting','anchor','')
    monkeypatch.setattr(search, '_prove_html_detail', lambda **kw: job)
    out=search.search_generic_origin(origin_url='https://acme.test/careers',query='',
        inventory_mode=True,execute=lambda req:('<html>careers</html>',req.url,200))
    assert out.jobs == (job,)
    with pytest.raises(ValueError):
        search.search_generic_origin(origin_url='https://acme.test',query='Hannover',
            inventory_mode=True,execute=lambda _:pytest.fail('network'))


def test_broad_record_keeps_evidence_and_honest_limit(monkeypatch):
    job=AcquiredJobPage('https://acme.test/job/1','https://acme.test/job/1',200,
        'Nurse Sydney',2000,'jsonld_jobposting','anchor','')
    outcome=search.GenericSearchOutcome('finite_inventory_local_filter','',1,1,(job,),False,'detail_cap','https://acme.test')
    monkeypatch.setattr(product,'search_generic_origin',lambda **kw:outcome)
    monkeypatch.setattr(product,'_detail_evidence',lambda **kw:{'status_code':200})
    source=SimpleNamespace(company_key='acme',company_name='Acme',candidate_id=1,candidate_url='https://acme.test')
    records,_=product.acquire_broad_records('generic_origin:acme',source)
    assert len(records)==1
    raw=records[0].raw_data
    assert raw['corpus_collection']['personal_filter'] is False
    assert raw['corpus_collection']['exhausted'] is False
    assert not raw.get('acquisition_boundary',{}).get('query_semantics_proven')
    assert raw['bronze_admission']['status']=='pass'


def test_broad_silver_normalizes_even_without_personal_matches(monkeypatch):
    decisions=[];written=[]
    class Repo:
        def load_unprocessed_raw_jobs(self,**kw):
            assert kw['broad_corpus'] is True
            return [dict(id=1,source_name='generic_origin:acme',raw_data={})]
        def record_processing_decision(self,**kw):decisions.append(kw)
    monkeypatch.setattr(silver,'SilverJobRepository',Repo)
    monkeypatch.setattr(silver,'is_relevant_for_silver',lambda _:False)
    monkeypatch.setattr(silver,'transform_raw_job_to_silver',lambda _:dict(raw_job_id=1,title='Nurse Sydney',company_name='Acme'))
    monkeypatch.setattr(silver,'write_silver_job_with_origin_locations',lambda *a,**kw:written.append(kw))
    result=silver.main(['--source','generic_origin:acme','--broad-corpus'])
    assert result==dict(selected=1,included=1,skipped=0)
    assert len(written)==1 and decisions[0]['reason']=='broad_corpus_normalized'
