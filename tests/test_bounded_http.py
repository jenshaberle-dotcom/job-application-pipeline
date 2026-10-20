from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import requests
from src.connectors.bounded_http import get_with_evidence


def response(status=200, headers=None):
    return SimpleNamespace(status_code=status, headers=headers or {}, content=b"page",
                           encoding="utf-8", url="https://example.org", close=Mock())


def run(items, limit=4):
    session=SimpleNamespace(get=Mock(side_effect=items))
    calls, waits = [], []
    value=get_with_evidence(session,"https://example.org",timeout=2,calls=calls,
                            limit=limit,shape=lambda u:u,max_body_bytes=100,sleep=waits.append)
    return value,calls,waits


def test_transient_get_retries_with_shared_evidence_budget():
    result,calls,waits=run([response(503),response()])
    assert result[2]==200 and len(calls)==2 and waits==[.25]


def test_timeout_attempt_is_counted():
    _,calls,_=run([requests.Timeout(),response()])
    assert calls[0]["error"]=="TIMEOUT" and len(calls)==2


@pytest.mark.parametrize("status,headers",[(403,{}),(404,{}),(429,{"Retry-After":"30"}),
                                           (503,{"Retry-After":"Wed, 21 Oct 2026 07:28:00 GMT"})])
def test_denial_and_server_delay_do_not_trigger_immediate_retry(status,headers):
    result,calls,waits=run([response(status,headers)])
    assert result[2]==status and len(calls)==1 and not waits


def test_budget_prevents_retry():
    result,calls,waits=run([response(503)],limit=1)
    assert result[2]==503 and len(calls)==1 and not waits


def test_tls_failure_not_retried():
    with pytest.raises(requests.exceptions.SSLError):
        run([requests.exceptions.SSLError("untrusted")])


def test_redirects_consume_same_budget():
    result,calls,_=run([response(302,{"Location":"/careers"}),response()])
    assert result[2]==200 and len(calls)==2
    assert calls[1]["requested"]=="https://example.org/careers"


def test_redirect_loop_cannot_exceed_budget():
    with pytest.raises(RuntimeError,match="cap exceeded"):
        run([response(302,{"Location":"/"}),response(302,{"Location":"/"})],limit=2)


def test_https_downgrade_is_rejected():
    with pytest.raises(RuntimeError,match="invalid HTTPS"):
        run([response(302,{"Location":"http://example.org"})])
