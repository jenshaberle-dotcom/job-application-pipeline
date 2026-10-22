"""Bounded repair of a stale entry URL; TLS verification remains mandatory."""
from urllib.parse import urlparse
import requests


def alternatives(url):
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port:
        return ()
    host = p.hostname
    # Only the same host's root and its conventional www/apex spelling.
    # No guessed parent domain, alternate TLD, HTTP downgrade or third party.
    other = host[4:] if host.startswith("www.") else "www." + host
    result = []
    if p.path not in ("", "/") or p.query:
        result.append(p._replace(path="/", query="", fragment="").geturl())
    result.append(p._replace(netloc=other, fragment="").geturl())
    return tuple(result)


def fetch_entry(fetcher, url):
    try:
        first = fetcher(url)
    except (requests.ConnectionError, requests.Timeout) as error:
        first = None
        original_error = error
    else:
        if first[2] not in (404, 410):
            return first  # Never work around 401/403/429.
    for candidate in alternatives(url):
        try:
            result = fetcher(candidate)
        except (requests.RequestException, RuntimeError):
            continue
        if 200 <= result[2] < 300:
            return result
    if first is not None:
        return first
    raise original_error
