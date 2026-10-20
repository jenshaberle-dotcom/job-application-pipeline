import argparse
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import requests
from src.connectors.origin_entry_recovery import fetch_entry, alternatives
from src.connectors.employer_origin_acquisition_v4 import acquire_genuine_job_pages
from src.search_intelligence.origin_candidate_plan_v2 import generate_company_url_candidates_v2
from src.search_intelligence.origin_source_discovery_agent import probe_result_from_http_response
from scripts import run_deterministic_connector_builder_layer_audit as layers

ROOT = "https://employer.example/"
DETAIL = ROOT+"jobs/platform-engineer-12345"
JOB = '<script type="application/ld+json">{"@type":"JobPosting","title":"Engineer","description":"Build services","hiringOrganization":{"@type":"Organization","name":"Employer"}}</script>'


def test_observed_multiple_listing_hops_reach_real_job():
    pages = {ROOT:'<a href="/careers">Careers</a>',
             ROOT+"careers":'<a href="/careers/vacancies">Open positions</a>',
             ROOT+"careers/vacancies":f'<a href="{DETAIL}">Engineer</a>', DETAIL:JOB}
    calls=[]
    def fetch(url):
        calls.append(url)
        return pages[url],url,200
    jobs,_=acquire_genuine_job_pages(listing_url=ROOT,known_detail_urls=(),allowed_hosts=("employer.example",),
                                    fetcher=fetch,max_followup_requests=6,max_results=1)
    assert len(jobs)==1 and jobs[0].final_url==DETAIL, calls
    assert len(calls)==4


def test_bad_observed_link_does_not_erase_other_paths():
    def fetch(url):
        if url==ROOT:return '<a href="/jobs/broken-12345">Role</a><a href="'+DETAIL+'">Engineer</a>',url,200
        if "broken" in url:raise requests.Timeout()
        return JOB,url,200
    jobs,_=acquire_genuine_job_pages(listing_url=ROOT,known_detail_urls=(),allowed_hosts=("employer.example",),
                                    fetcher=fetch,max_followup_requests=3,max_results=1)
    assert len(jobs)==1


def test_sitemap_index_to_list_to_detail_keeps_authority():
    pages={ROOT:"<html>Home</html>",ROOT+"sitemap.xml":
           '<sitemapindex><sitemap><loc>'+ROOT+'jobs-sitemap.xml</loc></sitemap></sitemapindex>',
           ROOT+"jobs-sitemap.xml":'<urlset><url><loc>'+DETAIL+'</loc></url></urlset>',DETAIL:JOB}
    jobs,_=acquire_genuine_job_pages(listing_url=ROOT,known_detail_urls=(),allowed_hosts=("employer.example",),
                                    fetcher=lambda u:(pages[u],u,200),max_followup_requests=6,max_results=1)
    assert len(jobs)==1


def test_sitemap_never_grants_external_host():
    from src.connectors.employer_origin_sitemap_navigation import sitemap_navigation
    assert sitemap_navigation(sitemap_url=ROOT+"sitemap.xml",allowed_hosts=("employer.example",),
        body='<sitemapindex><sitemap><loc>https://other.example/jobs.xml</loc></sitemap></sitemapindex>')==()


def test_origin_resolution_cached_within_assessment_only(monkeypatch):
    args=argparse.Namespace(_origin_cache={})
    probe=Mock(return_value=(ROOT,{}))
    monkeypatch.setattr(layers,"_resolve_origin_uncached",probe)
    row=dict(company_key="abc",company_name="Employer")
    assert layers._resolve_origin(row,args)==layers._resolve_origin(row,args)
    assert probe.call_count==1
    layers._resolve_origin(dict(row,company_key="different"),args)
    assert probe.call_count==2


def test_brand_before_description_is_a_hypothesis_not_approval():
    candidates=generate_company_url_candidates_v2(company_key="census-"+"a"*64,
                 company_name="Novalux Systemhaus GmbH",max_candidates=12)
    assert "https://novalux.de/" in [c.url for c in candidates]


def test_styles_do_not_hide_actual_navigation_and_scripts_are_not_career_evidence():
    def probe(text):
        return probe_result_from_http_response(ROOT,SimpleNamespace(status_code=200,url=ROOT,text=text,content=text.encode()))
    assert probe("<style>"+"x"*12000+"</style><a>Karriere</a>").career_like
    assert not probe("<script>let x='karriere jobs careers'</script><h1>Home</h1>").career_like


def test_stale_path_uses_same_verified_host_root():
    fetch=Mock(side_effect=[("",ROOT+"old",404),("home",ROOT,200)])
    assert fetch_entry(fetch,ROOT+"old")[2]==200
    assert fetch.call_args_list[1].args==(ROOT,)


@pytest.mark.parametrize("status",[401,403,429])
def test_denials_not_worked_around(status):
    fetch=Mock(return_value=("",ROOT,status))
    assert fetch_entry(fetch,ROOT)[2]==status and fetch.call_count==1


def test_tls_failure_can_try_verified_apex_but_never_disable_tls():
    fetch=Mock(side_effect=[requests.exceptions.SSLError(),("home",ROOT,200)])
    assert fetch_entry(fetch,"https://www.employer.example/")[2]==200
    assert fetch.call_args_list[1].args==(ROOT,)
    assert alternatives("http://employer.example/")==()
    assert alternatives("https://user:password@employer.example/")==()


def test_full_factory_stale_entry_through_career_chain_to_strict_proof(monkeypatch):
    pages={ROOT+"old":("",404), ROOT:('<a href="/careers">Careers</a>',200),
           ROOT+"careers":('<a href="/careers/vacancies">Open positions</a>',200),
           ROOT+"careers/vacancies":(f'<a href="{DETAIL}">Engineer</a>',200), DETAIL:(JOB,200)}
    def get(url, **kwargs):
        body,status=pages[url]
        return SimpleNamespace(content=body.encode(),url=url,status_code=status,
                               headers={},encoding="utf-8",close=lambda:None)
    session=SimpleNamespace(headers={},get=Mock(side_effect=get))
    monkeypatch.setattr(layers.requests,"Session",lambda:session)
    args=argparse.Namespace(target_location="",origin_timeout_seconds=5,origin_max_candidates=12,
                           http_timeout_seconds=10,acquisition_get_cap=12,navigation_hops=6)
    result=layers._assessment(dict(id=1,company_key="employer",company_name="Employer",
                                   candidate_url=ROOT+"old"),args)
    assert result.first_failure is None
    assert session.get.call_count==5


@pytest.mark.parametrize("bad", ["https://[broken/jobs/a", "https://[xyz]/jobs/a"])
def test_malformed_anchor_and_embedded_url_do_not_abort_good_detail(bad):
    root_html = f'<a href="{bad}">Invalid</a><script>let u="{bad}"</script><a href="{DETAIL}">Engineer</a>'
    calls=[]
    def fetch(u):
        calls.append(u)
        return (root_html if u==ROOT else JOB),u,200
    jobs,_=acquire_genuine_job_pages(listing_url=ROOT,known_detail_urls=(),allowed_hosts=("employer.example",),
                                    fetcher=fetch,max_followup_requests=6,max_results=1)
    assert len(jobs)==1 and calls==[ROOT,DETAIL]


def test_career_language_fanout_preserves_sitemap_route_with_same_budget():
    languages=["de", "en", "es", "fr", "it", "nl"]
    links="".join(f'<a href="/{lang}/careers">Careers</a>' for lang in languages)
    pages={ROOT:links, **{ROOT+lang+"/careers":links for lang in languages},
           ROOT+"sitemap.xml":'<urlset><url><loc>'+DETAIL+'</loc></url></urlset>',DETAIL:JOB}
    calls=[]
    def fetch(u):
        calls.append(u)
        return pages[u],u,200
    jobs,_=acquire_genuine_job_pages(listing_url=ROOT,known_detail_urls=(),allowed_hosts=("employer.example",),
                                    fetcher=fetch,max_followup_requests=6,max_results=1)
    assert len(jobs)==1
    assert ROOT+"sitemap.xml" in calls and len(calls)<=7


def test_cms_oembed_job_url_is_not_a_vacancy_request():
    metadata=ROOT+"wp-json/oembed/1.0/embed?url="+DETAIL
    root_html=f'<a href="{metadata}">Jobs</a><a href="{DETAIL}">Engineer</a>'
    calls=[]
    def fetch(u):
        calls.append(u)
        assert u!=metadata
        return (root_html if u==ROOT else JOB),u,200
    jobs,_=acquire_genuine_job_pages(listing_url=ROOT,known_detail_urls=(),allowed_hosts=("employer.example",),
                                    fetcher=fetch,max_followup_requests=6,max_results=1)
    assert len(jobs)==1
