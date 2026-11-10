"""Two fixed anonymous HTTPS reads; no proxy, redirects, subprocess or credential use."""
import hashlib
import http.client
import ipaddress
import json
import queue
import re
import socket
import ssl
import threading
from urllib.parse import urlsplit

MANIFEST='https://storage.stapply.ai/jobhive/v1/manifest.json'
DIRECTORY='https://storage.stapply.ai/jobhive/v1/companies.csv'
LIMITS={MANIFEST:512*1024,DIRECTORY:16*1024**2}

def need(ok,code):
    if not ok: raise ValueError(code)

def public_addresses(rows):
    addresses=sorted({r[4][0] for r in rows})
    need(bool(addresses),'DNS_EMPTY')
    need(all(ipaddress.ip_address(a).version==4 and ipaddress.ip_address(a).is_global
             and not ipaddress.ip_address(a).is_multicast for a in addresses),'DNS_NONPUBLIC')
    return addresses

def resolve(host):
    box=queue.Queue(maxsize=1)
    def work():
        try:box.put((True,socket.getaddrinfo(host,443,socket.AF_INET,socket.SOCK_STREAM)))
        except Exception as e:box.put((False,type(e).__name__))
    threading.Thread(target=work,daemon=True).start()
    try:ok,rows=box.get(timeout=10)
    except queue.Empty:raise ValueError('DNS_TIMEOUT') from None
    need(ok,'DNS_LOOKUP_FAILED')
    return public_addresses(rows)

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,ip):
        ctx=ssl.create_default_context(cafile='/etc/ssl/certs/ca-certificates.crt')
        ctx.minimum_version=ssl.TLSVersion.TLSv1_2
        ctx.set_alpn_protocols(['http/1.1'])
        super().__init__(host,443,timeout=15,context=ctx)
        self.pinned_ip=ip
    def connect(self):
        need(not self._tunnel_host,'TUNNEL_DENIED')
        raw=socket.socket(socket.AF_INET,socket.SOCK_STREAM);raw.settimeout(15)
        try:
            raw.connect((self.pinned_ip,443))
            need(raw.getpeername()[0]==self.pinned_ip,'PEER_BINDING')
            self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException:
            raw.close();raise

def read_response(response,limit):
    need(response.status==200,'DIRECTORY_HTTP_STATUS_'+str(response.status))
    need(response.getheader('Content-Encoding','identity').lower()=='identity','ENCODING_DENIED')
    length=response.getheader('Content-Length')
    if length is not None:
        need(length.isdigit() and int(length)<=limit,'CONTENT_LENGTH_BUDGET')
    chunks=[];total=0
    while True:
        part=response.read(min(65536,limit+1-total))
        if not part:break
        chunks.append(part);total+=len(part)
        need(total<=limit,'BODY_BUDGET')
    need(length is None or total==int(length),'BODY_TRUNCATED')
    return b''.join(chunks)

class DirectoryTransport:
    def __init__(self):self.receipts=[];self.attempted=[]
    def get(self,url):
        need(url in LIMITS and url not in self.attempted,'FIXED_READ_ONCE_ONLY')
        self.attempted.append(url);p=urlsplit(url);ips=resolve(p.hostname)
        conn=PinnedHTTPS(p.hostname,ips[0])
        # Bound slow headers/bodies as well as per-socket inactivity.
        def cancel():
            try:
                if conn.sock:conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            conn.close()
        timer=threading.Timer(75,cancel);timer.daemon=True;timer.start()
        try:
            conn.request('GET',p.path,headers={'Accept-Encoding':'identity','User-Agent':'RCC-JAP-directory-review/0.12.19','Connection':'close'})
            response=conn.getresponse();body=read_response(response,LIMITS[url])
            self.receipts.append(dict(url=url,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),
                http_status=response.status,tls_hostname_verified=True,public_ipv4_pinned=True))
            return body
        finally:timer.cancel();conn.close()

def manifest_entry(raw):
    need(len(raw)<=LIMITS[MANIFEST],'MANIFEST_BUDGET')
    value=json.loads(raw);entry=value.get('companies') if isinstance(value,dict) else None
    need(isinstance(entry,dict),'MANIFEST_COMPANIES')
    need(entry.get('csv')==DIRECTORY,'MANIFEST_FIXED_CSV_URL')
    need(type(entry.get('rows')) is int and 0<entry['rows']<=200000,'MANIFEST_ROWS')
    digest=entry.get('sha256')
    need(isinstance(digest,str) and re.fullmatch('[0-9a-fA-F]{64}',digest),'MANIFEST_DIGEST')
    return entry

def verify_download(entry,raw,raw_rows):
    need(len(raw)<=LIMITS[DIRECTORY],'DIRECTORY_BUDGET')
    need(hashlib.sha256(raw).hexdigest()==entry['sha256'].lower(),'DIRECTORY_MANIFEST_HASH_MISMATCH')
    need(raw_rows==entry['rows'],'DIRECTORY_MANIFEST_ROW_MISMATCH')
