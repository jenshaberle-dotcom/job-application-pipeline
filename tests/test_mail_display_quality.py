from scripts.product_v1_f5_application_tracking_runtime import _display_identity,build_application_tracking_payload
from src.search_intelligence.application_event_classifier import classify_application_evidence


def test_pronoun_is_not_an_employer_and_missing_title_is_not_invented():
    assert _display_identity(None,'uns') == (None,None,['employer_identity_missing','job_title_missing'])


def test_remove_only_exact_employer_suffix():
    assert _display_identity('Projektmanager (w/m/d) bei Example GmbH','Example GmbH')[0]=='Projektmanager (w/m/d)'
    assert _display_identity('Engineer at Other','Example GmbH')[0]=='Engineer at Other'


def test_unmatched_messages_and_missing_identity_are_review_items():
    result=build_application_tracking_payload(applications=[dict(application_id=1,discovery_kind='mailbox_observed',job_identity_snapshot={'company_name':'uns'})],candidates=[dict(candidate_id=1,candidate_class='rejection')])
    assert len(result['applications'])==1
    assert result['applications'][0]['company_name'] is None
    assert result['summary']['review_item_count']==2


def test_explicit_rejection_beats_boilerplate_acknowledgement():
    result=classify_application_evidence(subject='Ihre Bewerbung',text_excerpt='Vielen Dank für Ihre Bewerbung. Wir haben uns für eine andere Kandidatin entschieden.')
    assert result.candidate_class=='rejection'


def test_decision_without_recruiting_context_does_not_close_application():
    result=classify_application_evidence(subject='Vereinswahl',text_excerpt='Wir haben uns für eine andere Kandidatin entschieden.')
    assert result.candidate_class!='rejection'
