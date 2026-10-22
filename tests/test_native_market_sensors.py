from types import SimpleNamespace
import pytest
from scripts import run_native_market_sensors as worker


def test_plan_uses_only_recurring_active_sensor_profiles(monkeypatch):
    profiles=[SimpleNamespace(profile_name="ba",source_name="bundesagentur_fuer_arbeit"),
              SimpleNamespace(profile_name="paused",source_name="stepstone"),
              SimpleNamespace(profile_name="origin",source_name="generic_origin:test")]
    repo=SimpleNamespace(load_active_search_profiles=lambda:profiles,
                         load_recurring_search_profile_names=lambda:{"ba","origin"},
                         load_active_search_terms=lambda name:[("profile","term")])
    tasks=worker.plan(repo)
    assert len(tasks)==1 and tasks[0][0].profile_name=="ba"


def test_plan_refuses_unbounded_or_empty_term_population():
    profile=SimpleNamespace(profile_name="ba",source_name="bundesagentur_fuer_arbeit")
    repo=SimpleNamespace(load_active_search_profiles=lambda:[profile],
                         load_recurring_search_profile_names=lambda:{"ba"},
                         load_active_search_terms=lambda name:[("p","t")]*101)
    with pytest.raises(RuntimeError,match="BUDGET"):
        worker.plan(repo)


def test_failed_term_does_not_abort_other_terms_or_activate_sources(tmp_path, monkeypatch):
    from contextlib import contextmanager
    statements=[]
    class Database:
        def execute(self, sql, args=()):
            statements.append((sql,args))
            if "SELECT DISTINCT normalized" in sql:
                return SimpleNamespace(fetchall=lambda:[("known",)])
            if "SELECT DISTINCT e." in sql:
                return SimpleNamespace(fetchall=lambda:[("known","Known"),("new","New")])
            if "SELECT 1 FROM employer" in sql:
                return SimpleNamespace(fetchone=lambda:(1,) if args[0]=="known" else None)
            return SimpleNamespace(fetchone=lambda:None)
    @contextmanager
    def connection():
        yield Database()
    repo=SimpleNamespace(get_connection=connection)
    profile=SimpleNamespace(profile_name="ba",source_name="bundesagentur_fuer_arbeit")
    calls=[]
    class Runner:
        def __init__(self,*a,**kw):
            assert kw["source_role"]==worker.SourceRole.SENSOR
        def run_market_sensor_observation(self, terms):
            calls.append(terms)
            if len(calls)==1:
                raise TimeoutError()
    monkeypatch.setattr(worker,"JobIngestionRunner",Runner)
    monkeypatch.setattr(worker,"create_connector",lambda _:None)
    monkeypatch.setattr(worker,"checked_source",lambda:"a"*40)
    result=worker.execute(repo,[(profile,("p","one")),(profile,("p","two"))],tmp_path)
    assert result["successful_terms"]==1 and result["failed_terms"]==1
    assert result["new_market_companies"]==1 and result["discovery_candidates_created"]==1
    assert result["product_jobs_written"]==0 and result["sources_activated"]==0
    inserted=[args for sql,args in statements if sql.lstrip().startswith("INSERT")]
    assert len(inserted)==1 and inserted[0][:2]==("new","New")
