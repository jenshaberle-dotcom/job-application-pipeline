import pytest
from scripts.product_v1_operator_status import parse_operator_status, append_status
from scripts.product_v1_f5_application_actions import canonical_sha256, ApplicationActionError
from scripts.product_v1_f5_application_tracking_runtime import build_application_tracking_payload

def request(**overrides):
    return parse_operator_status(dict(application_id=1, status='withdrawn', reason='Distance',
        expected_identity_sha256=canonical_sha256({'title':'Engineer'}), expected_revision=0,
        request_id='a'*32, **overrides))

def test_append_retry_and_stale_concurrent_change():
    req=request()
    provenance, changed=append_status({}, {'title':'Engineer'}, req)
    assert changed and len(provenance['operator_status_events'])==1
    assert append_status(provenance, {'title':'Engineer'}, req)==(provenance,False)
    from dataclasses import replace
    with pytest.raises(ApplicationActionError):
        append_status(provenance, {'title':'Engineer'}, replace(req,request_id='b'*32))
    with pytest.raises(ApplicationActionError):
        append_status({}, {'title':'Different'}, req)

def test_manual_withdrawal_overrides_old_mail_and_can_be_released():
    row=dict(application_id=1, title='Engineer', company_name='Employer', effective_stage='interview',
        observed_stage='interview', job_identity_snapshot={'title':'Engineer'},
        operator_provenance={'operator_status_events':[{'status':'withdrawn','reason':'Distance'}]})
    result=build_application_tracking_payload(applications=[row], candidates=[])
    item=result['applications'][0]
    assert item['effective_stage']=='closed'
    assert item['observed_stage']=='interview'
    assert item['effective_stage_basis']=='operator_confirmed'
    row['operator_provenance']['operator_status_events'].append({'status':'automatic'})
    assert build_application_tracking_payload(applications=[row],candidates=[])['applications'][0]['effective_stage']=='interview'

@pytest.mark.parametrize('status', ['deleted','sent',''])
def test_invalid_status(status):
    with pytest.raises(ApplicationActionError):
        parse_operator_status({'status':status})
