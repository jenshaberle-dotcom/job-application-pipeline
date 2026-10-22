from contextlib import nullcontext
from types import SimpleNamespace
import pytest
from scripts import product_v1_f5_application_actions as actions
from scripts.run_product_mailbox_bridge import enrich_identity, install_policy
from src.search_intelligence.application_identity_matching import ExistingApplicationIdentity, match_existing_application_identity
from src.search_intelligence.application_event_classifier import classify_application_evidence


@pytest.mark.parametrize('text', [
    'Wir müssen dir leider mitteilen, dass wir deine Bewerbung nicht weiter in der engeren Auswahl berücksichtigen konnten.',
    'Leider müssen wir Ihnen heute mitteilen, dass Ihre Bewerbung nicht in die engere Auswahl gekommen ist.',
])
def test_shortlist_rejection_overrides_polite_receipt(text):
    result = classify_application_evidence(subject='Ihre Bewerbung auf unsere Stelle Systemtester Maschinen- und Anlagentechnik (m/w/d)',
        text_excerpt='Vielen Dank für Ihre Bewerbung. ' + text)
    assert result.candidate_class == 'rejection'
    assert result.authority == 'evidence_only'


@pytest.mark.parametrize('text', [
    'Ihre Bewerbung ist in die engere Auswahl gekommen.',
    'Ihre Bewerbung ist noch nicht abschließend geprüft. Die engere Auswahl treffen wir morgen.',
    'Bitte sagen Sie uns, falls Sie Ihre Bewerbung nicht weiter verfolgen möchten.',
])
def test_pending_or_positive_shortlist_is_not_rejection(text):
    assert classify_application_evidence(subject='Ihre Bewerbung', text_excerpt=text).candidate_class != 'rejection'


def test_explicit_position_subject_recovers_missing_title_without_changing_employer():
    row = dict(subject='AW: Ihre Bewerbung auf unsere Stelle Systemtester Maschinen- und Anlagentechnik (m/w/d)',
        employer_name='Bundesdruckerei-Gruppe', job_title=None)
    enriched = enrich_identity(row)
    assert enriched['job_title'] == 'Systemtester Maschinen- und Anlagentechnik (m/w/d)'
    assert enriched['employer_name'] == row['employer_name']
    assert row['job_title'] is None
    assert enrich_identity({**row, 'job_title': 'Manuell korrigierter Titel'})['job_title'] == 'Manuell korrigierter Titel'


def test_search_policy_covers_truncated_shortlist_outcomes_without_generic_withdrawal_phrase():
    bridge = SimpleNamespace(_GMAIL_SEARCH_SIGNAL_QUERIES=(('rejection', '{"old"}'), ('withdrawal_confirmation', '{"withdrawal of application"}')),
        _impl=SimpleNamespace(normalize_gmail_message=lambda row: row))
    install_policy(bridge)
    queries = dict(bridge._GMAIL_SEARCH_SIGNAL_QUERIES)
    assert '"Bewerbung nicht in die engere Auswahl gekommen"' in queries['rejection']
    assert '"Bewerbung nicht weiter in der engeren Auswahl berücksichtigen"' in queries['rejection']
    assert '"meine Bewerbung"' not in queries['withdrawal_confirmation']


def test_subject_restores_role_and_rejects_boilerplate_employer():
    row = dict(subject='Deine Bewerbung bei Example als AI Automation Architect - SDLC', employer_name='uns', job_title=None)
    enriched = enrich_identity(row)
    assert enriched['employer_name'] == 'Example'
    assert enriched['job_title'] == 'AI Automation Architect - SDLC'
    assert row['job_title'] is None


def test_subject_without_role_does_not_invent_title():
    assert enrich_identity(dict(subject='Deine Bewerbung bei Example',employer_name='uns')).get('job_title') is None


def test_technical_abbreviation_matches_unique_employer_role_only():
    app = ExistingApplicationIdentity('one','Example GmbH','AI Automation Architect - Software Development Lifecycle - Germany - Example',None)
    kwargs=dict(employer_name='Example',job_title='AI Automation Architect - SDLC',source_url=None)
    assert match_existing_application_identity(**kwargs,applications=[app])[0]=='one'
    assert match_existing_application_identity(**{**kwargs,'employer_name':'Other'},applications=[app])[0] is None
    assert match_existing_application_identity(**kwargs,applications=[app,app])[1] is True


def test_policy_keeps_metadata_transport_and_extends_specific_rejection_search():
    normalize=lambda row: row
    bridge=SimpleNamespace(_GMAIL_SEARCH_SIGNAL_QUERIES=(('rejection','{"existing phrase"}'),),_impl=SimpleNamespace(normalize_gmail_message=normalize))
    install_policy(bridge)
    assert 'müssen wir dir leider absagen' in bridge._GMAIL_SEARCH_SIGNAL_QUERIES[0][1]
    assert set(vars(bridge._impl)) == {'normalize_gmail_message'}


@pytest.mark.parametrize('stale',[False,True])
def test_missing_title_uses_identity_revision_not_display_label(monkeypatch,stale):
    snapshot={'employer_name':'uns','job_title':None}
    writes=[]
    class Cursor:
        rowcount=1
        def execute(self,sql,params):
            if 'UPDATE applications' in sql: writes.append(params)
        def fetchone(self):
            return dict(id=1,discovery_kind='mailbox_observed',job_identity_snapshot=snapshot,job_identity_sha256=actions.canonical_sha256(snapshot),provenance={})
    cursor=Cursor()
    conn=SimpleNamespace(transaction=lambda:nullcontext(),cursor=lambda:nullcontext(cursor))
    monkeypatch.setattr(actions.psycopg,'connect',lambda *a,**k:nullcontext(conn))
    monkeypatch.setattr(actions.DatabaseConfig,'from_environment',lambda:SimpleNamespace(dsn=lambda:'test'))
    request=actions.parse_application_title_correction_request(dict(action=actions.CORRECT_TITLE_ACTION_NAME,application_id=1,job_title='Engineer',expected_identity_sha256='0'*64 if stale else actions.canonical_sha256(snapshot)))
    if stale:
        with pytest.raises(actions.ApplicationActionError,match='identity_changed'):
            actions.correct_application_job_title(request)
        assert not writes
    else:
        assert actions.correct_application_job_title(request)['status']=='corrected'
        assert len(writes)==1
