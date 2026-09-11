from __future__ import annotations

from types import SimpleNamespace

from scripts import run_generic_employer_origin_product as product
from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    failed,
    not_reached,
    passed,
    skipped,
)


def _proof_residual() -> ConnectorBuilderAssessment:
    return ConnectorBuilderAssessment(
        candidate_id=83,
        company_key="example",
        company_name="Example GmbH",
        layers=(
            passed("identity", "identity proven"),
            passed(
                "origin",
                "persisted origin",
                source="persisted_candidate_url",
                candidate_url={
                    "scheme": "https",
                    "host": "example.test",
                    "path": "/karriere",
                    "query_keys": [],
                },
            ),
            passed("origin_reachability", "origin reachable"),
            skipped("delegation", "not required"),
            skipped("provider", "not required"),
            passed("inventory", "inventory exposed"),
            passed("detail", "detail exposed"),
            failed("proof", "baseline proof residual"),
            not_reached("recipe", "proof failed"),
        ),
    )


def test_bite_residual_promotes_only_proof_failure_via_existing_strict_proof(monkeypatch) -> None:
    baseline = _proof_residual()
    proven_job = SimpleNamespace(
        job=SimpleNamespace(
            final_url="https://jobs.example.test/jobposting/abc",
            proof_kind="known_detail_and_job_content",
        )
    )
    inventory = SimpleNamespace(
        postings=(object(), object()),
        employer_page_url="https://example.test/karriere/stellenangebote",
    )

    monkeypatch.setattr(
        product.layer_core,
        "_resolve_origin",
        lambda row, args: ("https://example.test/karriere", "persisted_candidate_url"),
    )
    monkeypatch.setattr(
        product,
        "prove_one_bite_source",
        lambda *, origin_url: (proven_job, inventory),
    )

    result = product._bite_residual({}, SimpleNamespace(), baseline)

    assert result.layers[7].state.value == "pass"
    assert result.layers[7].evidence["provider"] == "bite"
    assert result.layers[7].evidence["proof_kind"] == "known_detail_and_job_content"
    assert result.layers[8].state.value == "pass"
    assert result.layers[8].evidence["capability"] == "bite_finite_inventory_raw_detail"


def test_bite_residual_does_not_bypass_earlier_failure(monkeypatch) -> None:
    baseline = _proof_residual()
    layers = list(baseline.layers)
    layers[5] = failed("inventory", "inventory missing")
    layers[6] = not_reached("detail", "inventory failed")
    layers[7] = not_reached("proof", "inventory failed")
    layers[8] = not_reached("recipe", "inventory failed")
    blocked = ConnectorBuilderAssessment(
        baseline.candidate_id,
        baseline.company_key,
        baseline.company_name,
        tuple(layers),
    )

    called = False

    def unexpected(**kwargs):
        nonlocal called
        called = True
        return None

    monkeypatch.setattr(product, "prove_one_bite_source", unexpected)

    assert product._bite_residual({}, SimpleNamespace(), blocked) is blocked
    assert called is False
