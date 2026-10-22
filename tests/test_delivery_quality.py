from contextlib import contextmanager
from scripts.product_v1_delivery_quality import maintain_source
from scripts import run_product_v1_assessment_materialization as materializer
from scripts import run_f4b_affinity_authority as affinity

def test_closed_and_uncertain_jobs_never_scored_and_one_failure_isolated(monkeypatch):
    monkeypatch.setattr(materializer, 'authorized_recurring_employer_origin_sources', lambda _: {'example'})
    class DB:
        def execute(self,*args): return self
        def fetchall(self): return [{'silver_job_id':i} for i in range(1,5)]
    @contextmanager
    def connect(): yield DB()
    monkeypatch.setattr(affinity,'connect',connect)
    calls=[]
    class Journal:
        def stage(self,key,operation,*,effect):
            calls.append(key)
            assert effect
            if key.startswith('health:'):
                return {'outcome': {1:'closed',2:'unverifiable',3:'seen_active',4:'seen_active'}[int(key.split(':')[-1])]}
            if key=='assessment:example:3': raise ValueError('missing evidence')
            return {'changed':True}
    summary=maintain_source('example',Journal())
    assert summary['unavailable']==2 and summary['scored']==1
    assert len(summary['blocked'])==1
    assert 'affinity:example:3' not in calls
    assert 'assessment:example:1' not in calls
    assert 'assessment:example:2' not in calls
