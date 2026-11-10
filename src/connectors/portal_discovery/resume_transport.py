"""Reuse exact historical receipts; only missing observed targets get new GETs."""
import base64,gzip,hashlib
from .field_transport import Transport,target

class ResumeTransport(Transport):
    def __init__(self,report):
        super().__init__()
        self.bodies=dict(report['transport']['bodies_gzip_base64'])
        for sha,b in self.bodies.items():
            if hashlib.sha256(gzip.decompress(base64.b64decode(b))).hexdigest()!=sha:raise ValueError('RETAINED_BODY_CHANGED')
        self.records=[dict(r,observation_reused=True) for r in report['transport']['records']]
        self.cache={r['url']:r for r in self.records}
        self.sequence_offset=max(r['sequence'] for r in self.records)
        self.reused=0
    def fetch(self,url):
        u=target(url)
        if u in self.cache and self.cache[u].get('observation_reused'):self.reused+=1
        return super().fetch(url)
    def export(self):
        data=super().export();data['reused_receipt_reads']=self.reused
        data['attempts_meaning']='NEW_REQUESTS_ONLY';data['body_bytes_meaning']='NEW_BYTES_ONLY'
        data['retained_observations_are_not_fresh']=True
        return data
