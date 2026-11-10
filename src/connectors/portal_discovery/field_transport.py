"""Bounded anonymous public GETs. No provider endpoints, auth, cookies or proxies."""
import base64,gzip,hashlib,json,re,socket,threading,time
from urllib.parse import urlsplit,urlunsplit,urljoin
from datetime import datetime,timezone
from .family_contracts import public_url
from .directory_transport import PinnedHTTPS,resolve

MAX_ATTEMPTS=3500;MAX_BYTES=384*1024**2;MAX_RETAINED=96*1024**2;MAX_SECONDS=3600
BLOCKED=('openai.com','chatgpt.com','tavily.com','google.com','facebook.com','linkedin.com','github.com')

def target(value):
    u=public_url(value)
    if not u:raise ValueError('PUBLIC_URL_REQUIRED')
    p=urlsplit(u);h=p.hostname
    if any(h==x or h.endswith('.'+x) for x in BLOCKED):raise ValueError('PROVIDER_OR_SOCIAL_DISABLED')
    if re.search(r'/(?:auth|login|signin|sign-in|apply|application|bewerbungsformular|checkout|logout|delete)(?:/|$)',p.path,re.I):raise ValueError('NONREAD_ROUTE')
    if re.search(r'(?:token|password|secret|api_key|access_key)=',p.query,re.I):raise ValueError('CREDENTIAL_QUERY_DENIED')
    return urlunsplit(('https',h,p.path or '/',p.query,''))

class BudgetStop(ValueError):pass

class Transport:
    def __init__(self):
        self.records=[];self.bodies={};self.cache={};self.allowed=set();self.derivations=[]
        self.attempts=0;self.bytes=0;self.retained=0;self.started=time.monotonic();self.last_host={}
    def allow(self,url,kind,parent=None):
        u=target(url);self.allowed.add(u)
        self.derivations.append(dict(url=u,kind=kind,parent=parent));return u
    def body(self,receipt):return gzip.decompress(base64.b64decode(self.bodies[receipt['body_sha256']])) if receipt.get('body_sha256') else b''
    def check(self):
        if self.attempts>=MAX_ATTEMPTS or self.bytes>=MAX_BYTES or self.retained>=MAX_RETAINED or time.monotonic()-self.started>=MAX_SECONDS:raise BudgetStop('GLOBAL_READ_BUDGET')
    def fetch(self,url):
        u=target(url)
        if u not in self.allowed:raise ValueError('UNADMITTED_READ_TARGET')
        if u in self.cache:return self.cache[u],self.body(self.cache[u])
        self.check();self.attempts+=1;p=urlsplit(u)
        row=dict(url=u,sequence=getattr(self,'sequence_offset',0)+self.attempts,status=None,observed_at_utc=datetime.now(timezone.utc).isoformat(),content_type='',bytes=0)
        self.records.append(row);self.cache[u]=row
        conn=None;timer=None
        try:
            ips=resolve(p.hostname);delay=.2-(time.monotonic()-self.last_host.get(p.hostname,0))
            if delay>0:time.sleep(delay)
            self.last_host[p.hostname]=time.monotonic();conn=PinnedHTTPS(p.hostname,ips[0])
            def cancel():
                try:
                    if conn.sock:conn.sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                conn.close()
            timer=threading.Timer(25,cancel);timer.daemon=True;timer.start()
            conn.request('GET',p.path+('?' +p.query if p.query else ''),headers={'Accept-Encoding':'identity','User-Agent':'RCC-JAP-public-qualification/0.12.20','Connection':'close'})
            response=conn.getresponse();row['status']=response.status;row['content_type']=response.getheader('Content-Type','')[:200]
            if response.status in (301,302,303,307,308):
                row['redirect_target']=target(urljoin(u,response.getheader('Location','')));return row,b''
            if response.status!=200:return row,b''
            if response.getheader('Content-Encoding','identity').lower()!='identity':raise ValueError('COMPRESSED_TRANSFER_DENIED')
            limit=min(8*1024**2 if 'json' in row['content_type'] or 'xml' in row['content_type'] else 2*1024**2,MAX_BYTES-self.bytes)
            length=response.getheader('Content-Length')
            if length is not None and (not length.isdigit() or int(length)>limit):raise ValueError('RESPONSE_BYTE_BUDGET')
            parts=[];total=0
            while True:
                # No global-byte overshoot, even on unknown Content-Length.
                if total>=limit:
                    if length is not None and total==int(length):break
                    raise ValueError('RESPONSE_BYTE_BUDGET')
                chunk=response.read(min(65536,limit-total))
                if not chunk:break
                total+=len(chunk);self.bytes+=len(chunk);row['bytes']=total;parts.append(chunk)
            if length is not None and total!=int(length):raise ValueError('RESPONSE_TRUNCATED')
            body=b''.join(parts);sha=hashlib.sha256(body).hexdigest();packed=gzip.compress(body,mtime=0)
            if sha not in self.bodies:
                if self.retained+len(packed)>MAX_RETAINED:raise BudgetStop('EVIDENCE_BYTE_BUDGET')
                self.bodies[sha]=base64.b64encode(packed).decode();self.retained+=len(packed)
            row.update(body_sha256=sha,tls_hostname_verified=True,public_ip_pinned=True)
            return row,body
        except BudgetStop:raise
        except Exception as e:
            row['error']=str(e)[:150] if isinstance(e,ValueError) else type(e).__name__
            return row,b''
        finally:
            if timer:timer.cancel()
            if conn:conn.close()
    def read(self,url):
        seen=set();u=url
        for _ in range(4):
            u=target(u)
            if u in seen:raise ValueError('REDIRECT_LOOP')
            seen.add(u);r,b=self.fetch(u)
            if not r.get('redirect_target'):return r,b
            u=self.allow(r['redirect_target'],'observed_http_redirect',r['sequence'])
        raise ValueError('REDIRECT_LIMIT')
    def export(self):return dict(attempts=self.attempts,body_bytes=self.bytes,compressed_evidence_bytes=self.retained,
        elapsed_seconds=round(time.monotonic()-self.started,3),records=self.records,bodies_gzip_base64=self.bodies,
        derivations=self.derivations,max_attempts=MAX_ATTEMPTS,max_body_bytes=MAX_BYTES,max_seconds=MAX_SECONDS,
        tavily_requests=0,model_tasks=0,credential_reads=0)
