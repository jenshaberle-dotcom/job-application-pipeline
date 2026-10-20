"""Dependency-free policy on top of requests; retry only read-only GETs.

Attempts (including failures) share the caller's acquisition budget.
Long Retry-After delays are returned to the caller, never shortened.
"""
import time
import socket
from urllib.parse import urljoin, urlparse
import requests

TRANSIENT_STATUS = frozenset({429, 502, 503, 504})


def connection_error_code(error):
    pending, seen = [error], set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, socket.gaierror) or type(item).__name__ == "NameResolutionError":
            return "DNS_ERROR"
        pending.extend(v for v in (getattr(item, "reason", None), item.__cause__,
                                   item.__context__) if isinstance(v, BaseException))
        pending.extend(v for v in item.args if isinstance(v, BaseException))
    return "TIMEOUT" if isinstance(error, requests.exceptions.Timeout) else "CONNECTION_ERROR"


def get_with_evidence(session, url, *, timeout, calls, limit, shape,
                      max_body_bytes, sleep=time.sleep):
    retries = 0
    current = url
    while True:
        if len(calls) >= limit:
            raise RuntimeError("absolute acquisition GET cap exceeded")
        record = {"requested": shape(current), "attempt": len(calls) + 1}
        calls.append(record)
        try:
            response = session.get(current, timeout=timeout, allow_redirects=False)
        except requests.exceptions.SSLError:
            record["error"] = "TLS_ERROR"
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as error:
            record["error"] = connection_error_code(error)
            if record["error"] != "DNS_ERROR" and retries == 0 and len(calls) < limit:
                retries += 1
                sleep(.25)
                continue
            raise
        body = response.content
        record.update(final=shape(str(response.url)), status=int(response.status_code),
                      body_bytes=len(body))
        if len(body) > max_body_bytes:
            record["error"] = "BODY_LIMIT"
            response.close()
            raise RuntimeError("response body cap exceeded")
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            target = urljoin(current, location) if location else ""
            parsed = urlparse(target)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                record["error"] = "REDIRECT_TARGET_INVALID"
                response.close()
                raise RuntimeError("invalid HTTPS redirect target")
            record["redirect"] = shape(target)
            response.close()
            current = target
            continue
        retry_after = response.headers.get("Retry-After")
        delay = .25
        if retry_after is not None:
            try:
                delay = float(retry_after)
            except (ValueError, TypeError):
                delay = None  # HTTP date: don't guess an earlier retry.
        if (response.status_code in TRANSIENT_STATUS and retries == 0
                and len(calls) < limit and delay is not None and 0 <= delay <= 2):
            response.close()
            retries += 1
            sleep(delay)
            continue
        result = body.decode(response.encoding or "utf-8", errors="replace"), str(response.url), int(response.status_code)
        response.close()
        return result
