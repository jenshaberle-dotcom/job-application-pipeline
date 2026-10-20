import argparse
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from src.search_intelligence.employer_binding import employer_binding, recipe_hint, identity
from scripts import run_generic_employer_origin_product as product
from src.search_intelligence.deterministic_connector_builder import ConnectorBuilderAssessment, LAYER_ORDER, passed

ROOT="https://employer.example/"
DETAIL=ROOT+"jobs/engineer-12345"
NAME="Example Systems GmbH"
HOME='<h1>Example Systems GmbH</h1><a href="/jobs/engineer-12345">Engineer</a>'
def job(name=NAME):
    return '<script type="application/ld+json">'+json.dumps({"@type":"JobPosting","title":"Engineer","description":"Build software","hiringOrganization":{"@type":"Organization","name":name}})+'</script>'


def test_exact_employer_legal_suffix_and_case():
    assert identity(NAME)==identity("EXAMPLE SYSTEMS")
    assert employer_binding(NAME,HOME,job("Example Systems"),ROOT,DETAIL)["status"]=="VERIFIED"


@pytest.mark.parametrize("name",["Getriebebau NORD", "NORD GmbH", "TÜV NORD", "TÜV NORD Service GmbH"])
def test_shared_token_and_unproven_group_relationship_never_qualify(name):
    b=employer_binding("TÜV NORD Mobilität GmbH & Co. KG",'<h1>TÜV NORD Mobilität GmbH & Co. KG</h1>',job(name),ROOT,DETAIL)
    assert b["status"]=="EMPLOYER_CONFLICT"


def test_incidental_body_mention_is_not_origin_identity():
    assert employer_binding(NAME,'<p>Our customer: Example Systems GmbH</p>',job(),ROOT,DETAIL)["status"]!="VERIFIED"


def test_missing_or_mixed_employers_require_review():
    for html in ('<h1>Engineer</h1>Apply now', job()+job("Other Company"), '<script type="application/ld+json">{</script>'+job()):
        assert employer_binding(NAME,HOME,html,ROOT,DETAIL)["status"]!="VERIFIED"


def result_with_recipe():
    b=employer_binding(NAME,HOME,job(),ROOT,DETAIL)
    recipe=dict(schema="employer_search_recipe.v1",company_key="key",root_url=ROOT,detail_url=DETAIL,employer_binding=b)
    return dict(company_key="key",company_name=NAME,layers=[dict(layer="recipe",evidence=dict(search_recipe=recipe))])


def test_reuse_is_bound_to_stable_identity_and_current_schema():
    r=result_with_recipe()
    assert recipe_hint(r,"key",NAME)
    assert recipe_hint(r,"other",NAME) is None
    assert recipe_hint(r,"key","Other Company") is None
    assert recipe_hint(dict(company_key="key",company_name=NAME,layers=[]),"key",NAME) is None
    r["layers"][0]["evidence"]["search_recipe"]["detail_url"]="https://evil.example/jobs/123"
    assert recipe_hint(r,"key",NAME) is None


def run_product(monkeypatch, html= None, prior=None):
    def response(url):
        body=HOME if url.rstrip('/')==ROOT.rstrip('/') else html if html is not None else job()
        return SimpleNamespace(url=url,content=body.encode(),encoding="utf-8",status_code=200,headers={},close=lambda:None)
    session=SimpleNamespace(headers={},get=Mock(side_effect=lambda u,**kw:response(u)))
    monkeypatch.setattr(product.layer_core.requests,"Session",lambda:session)
    args=argparse.Namespace(target_location="",origin_timeout_seconds=1,origin_max_candidates=12,http_timeout_seconds=1,acquisition_get_cap=12,navigation_hops=6)
    r=product.assess_candidate(dict(id=1,company_key="key",company_name=NAME,candidate_url=ROOT,previous_recipe_result=prior),args)
    return r,session


def test_factory_end_to_end_generates_receipt_only_with_current_employer(monkeypatch):
    r,session=run_product(monkeypatch)
    assert r.recipe_ready and product.proof_passed(r)
    assert recipe_hint(r.to_json(),"key",NAME)
    assert session.get.call_count==2


def test_reused_success_is_fetched_again_and_conflict_revokes_qualification(monkeypatch):
    r,session=run_product(monkeypatch,job("Other Company"),result_with_recipe())
    assert not r.recipe_ready and not product.proof_passed(r)
    assert r.first_failure.reason=="EMPLOYER_ATTRIBUTION_REVIEW_REQUIRED"
    assert session.get.call_count==2


def test_legacy_residual_success_cannot_bypass_employer_gate(monkeypatch):
    old=ConnectorBuilderAssessment(1,"key",NAME,tuple(passed(x,"legacy") for x in LAYER_ORDER))
    monkeypatch.setattr(product.layer_core,"_assessment",lambda row,args:old)
    for name in ("_workday_residual","_portal_residual","_bite_residual"):
        monkeypatch.setattr(product,name,lambda row,args,assessment:assessment)
    monkeypatch.setattr(product,"_public_feed_residual",lambda assessment,args:assessment)
    r=product.assess_candidate(dict(id=1,company_key="key",company_name=NAME),argparse.Namespace())
    assert not r.recipe_ready and not product.proof_passed(r)


def test_valid_receipt_is_revalidated_and_records_reuse(monkeypatch):
    r,session=run_product(monkeypatch,prior=result_with_recipe())
    assert r.recipe_ready and r.layers[-1].evidence["search_recipe_reused"] is True
    assert session.get.call_count==2


def test_missing_identity_on_previously_valid_detail_fails_closed(monkeypatch):
    r,_=run_product(monkeypatch,'<title>Engineer</title><p>Apply now and build software.</p>'*4,result_with_recipe())
    assert not r.recipe_ready


@pytest.mark.parametrize("value",[None, [], {"company_key":"key","company_name":NAME,"layers":None},
    {"company_key":"key","company_name":NAME,"layers":[None]}])
def test_malformed_receipts_never_grant_authority(value):
    assert recipe_hint(value,"key",NAME) is None
