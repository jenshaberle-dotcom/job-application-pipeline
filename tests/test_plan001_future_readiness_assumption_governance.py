from pathlib import Path


DOC = Path("docs/planning/active/future_readiness_and_assumption_governance.md")
RULES = Path("docs/reference/governance/workflow/rules001_project_rules_index.md")
ROADMAP = Path("docs/planning/active/roadmap.md")


def test_plan001_future_transition_sequence_is_documented() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "Build event-capable, but not event-driven yet." in text
    assert "Core Pipeline >90% maturity" in text
    assert "Cloud-ready Batch Pipeline" in text
    assert "DB-backed Outbox/Event Foundation" in text
    assert "Kafka Event Backbone" in text
    assert "Spark Analytics / Replay / Feature Layer" in text


def test_plan001_manual_market_observation_and_assumption_validation_are_documented() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "MARKET-003 Manual Market Observation" in text
    assert "ASSUMPTION-001 Simplification Validation Register" in text
    assert "manual observations" in text
    assert "company-name normalization" in text
    assert "StepStone mirroring assumptions" in text
    assert "Heuristics may start discovery" in text
    assert "must not become" in text


def test_plan001_white_whale_triage_is_documented() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "WHALE-001 White-Whale Backlog Triage" in text
    assert "After cloud readiness" in text
    assert "Only if measurable value is proven" in text
    assert "too much whale" in text


def test_plan001_is_linked_from_rules_and_roadmap() -> None:
    rules = RULES.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")

    assert "PLAN-001 Future Readiness and Assumption Governance" in rules
    assert "event-capable, but not event-driven yet" in rules
    assert "future_readiness_and_assumption_governance.md" in rules

    assert "PLAN-001 Future Readiness and Assumption Governance" in roadmap
    assert "MARKET-003 Manual Market Observation Foundation" in roadmap
    assert "ASSUMPTION-001 Simplification Validation Register" in roadmap
    assert "WHALE-001 White-Whale Backlog Triage" in roadmap


def test_market003a_manual_company_seed_register_is_documented() -> None:
    from pathlib import Path

    plan = Path("docs/planning/active/future_readiness_and_assumption_governance.md").read_text(encoding="utf-8")
    rules = Path("docs/reference/governance/workflow/rules001_project_rules_index.md").read_text(encoding="utf-8")

    assert "MARKET-003A Manual Company Observation Seed Register" in plan
    assert "not a pipeline input" in plan
    assert "not source-of-truth" in plan
    assert "not automatically truth" in plan
    assert "not a gate pass" in plan
    assert "not a Gold metric" in plan

    for company in (
        "Bahlsen",
        "GETEC",
        "MEDIFOX DAN",
        "goetel",
        "Dataciders",
        "Atos",
        "Sopra Steria",
        "QUNIS",
        "VALUE AG",
        "SVA",
        "ivv",
        "NETGO",
        "SPARETECH",
        "Thinkport",
        "NeoBIM",
        "Oviva",
        "Aignostics",
        "Veeva Systems",
        "Grafana Labs",
        "Concordia Versicherungen",
        "EEW Energy from Waste",
        "ISR Information Products",
    ):
        assert company in plan

    assert "Manual company group-by outputs belong to MARKET-003A" in rules
    assert "Company normalization or same-company" in rules
