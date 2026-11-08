"""Offline SIWC-compatible streaming contract. No network or OAuth tokens."""
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

from scripts.run_hannover_browser_agent import scout, Company


class FakeStream:
    def __init__(self, action):
        self.action = action

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        yield SimpleNamespace(type="response.output_text.delta",
                              delta=json.dumps(self.action))
        yield SimpleNamespace(type="response.completed",
                              response=SimpleNamespace(usage=SimpleNamespace(
                                  input_tokens=50, output_tokens=12)))


class FakeClient:
    def __init__(self, actions):
        self.actions = list(actions)
        self.requests = []
        self.responses = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return FakeStream(self.actions.pop(0))


class FakeSearch:
    def __init__(self):
        self.count = 0
        self.queries = []

    def search(self, query):
        self.count += 1
        self.queries.append(query)
        return {"query": query, "results": [
            {"url": "https://jobs.example.org/roles", "title": "Jobs"}
        ]}


class FakeBrowser:
    def __init__(self):
        self.allowed = set()
        self.visited = []
        self.denied_requests = 0

    def allow_search(self, result):
        self.allowed.update(x["url"] for x in result.get("results", []))

    def inspect(self, url):
        self.visited.append(url)
        return {"url": url, "title": "Careers",
                "page_text": "Live positions", "links": []}


def test_siwc_path_streams_without_unsupported_parameters():
    actions = [
        {"action": "search_web", "query": "Acme Jobs"},
        {"action": "open_page", "url": "https://jobs.example.org/roles"},
        {"action": "nominate_portal", "url": "https://jobs.example.org/roles"},
        {"action": "finish"},
    ]
    client = FakeClient(actions)
    fake_sdk = SimpleNamespace(OpenAI=lambda **kwargs: client)
    company = Company("acme", "Acme GmbH")
    with patch.dict(os.environ, {"JAP_SIWC_ACCESS_TOKEN": "opaque-local-oauth-token"}):
        with patch.dict(sys.modules, {"openai": fake_sdk}):
            result = scout(company, FakeSearch(), FakeBrowser(),
                           "gpt-6.1-sol", auth="chatgpt-plan")
    assert result["candidates"] == ["https://jobs.example.org/roles"]
    assert result["model_usage"]["input_tokens"] == 200
    for req in client.requests:
        assert req["store"] is False and req["stream"] is True
        assert isinstance(req["input"], list)
        assert "max_output_tokens" not in req
        assert "tools" not in req
        assert "previous_response_id" not in req
    assert "opaque-local-oauth-token" not in json.dumps(result)
