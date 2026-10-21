from dataclasses import replace
from tests.test_job_lifecycle_health_probe import target
from src.job_lifecycle_health import HttpProbeResult, classify_exact_detail
import pytest

@pytest.mark.parametrize('url,body', [
    ('https://example.jobs.personio.de/job/2767212?language=de','404 Diese URL existiert nicht'),
    ('https://example.wd5.myworkdayjobs.com/en-US/jobs/job/City/Engineer_123',"The page you are looking for doesn't exist. Search for Jobs"),
])
def test_exact_ats_error_is_closed(url,body):
    t=replace(target(), source_url=url)
    assert classify_exact_detail(t,HttpProbeResult(200,url,body,0)).outcome=='closed'
    assert classify_exact_detail(t,HttpProbeResult(200,'https://example.com/',body,1)).outcome=='unverifiable'

def test_generic_error_and_redirected_410_are_not_closure():
    t=target()
    assert classify_exact_detail(t,HttpProbeResult(404,t.source_url,'Diese URL existiert nicht',0)).outcome=='unverifiable'
    assert classify_exact_detail(t,HttpProbeResult(410,'https://example.com/', 'Gone',1)).outcome=='unverifiable'
