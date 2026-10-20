import argparse
from types import SimpleNamespace
from unittest.mock import Mock
from scripts import run_deterministic_connector_builder_layer_audit as factory


def test_retry_sitemap_and_genuine_detail_share_real_factory_budget(monkeypatch):
    root="https://employer.example/"
    detail=root+"jobs/platform-engineer-12345"
    def response(url,body,status=200):
        return SimpleNamespace(url=url,content=body.encode(),encoding="utf-8",
                               status_code=status,headers={},close=lambda:None)
    session=SimpleNamespace(headers={}, get=Mock(side_effect=[
        response(root,"Busy",503), response(root,"<html>Employer home</html>"),
        response(root+"sitemap.xml",f"<urlset><url><loc>{detail}</loc></url></urlset>"),
        response(detail,'<script type="application/ld+json">'
                 '{"@type":"JobPosting","title":"Platform Engineer",'
                 '"description":"Build services","hiringOrganization":'
                 '{"@type":"Organization","name":"Employer"}}</script>'),
    ]))
    monkeypatch.setattr(factory.requests,"Session",lambda:session)
    args=argparse.Namespace(target_location="",origin_timeout_seconds=1,
                            origin_max_candidates=12,http_timeout_seconds=1)
    result=factory._assessment(dict(id=1,company_key="employer",company_name="Employer",
                                    candidate_url=root),args)
    assert result.first_failure is None
    assert session.get.call_count==4
