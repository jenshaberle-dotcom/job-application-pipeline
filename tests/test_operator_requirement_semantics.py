# Exact-head qualification marker for the R4 evidence-observer contract.
from src.silver.operator_requirement_semantics import (
    ObservedFact,
    collect_observed_facts,
    infer_posting_language,
    normalize_employment_scope,
    observed_facts_by_field,
)


def test_employment_scope_preserves_workload_without_contract_inference() -> None:
    assert normalize_employment_scope(["FULL_TIME"]) == "full_time"
    assert normalize_employment_scope(["PART_TIME"]) == "part_time"
    assert normalize_employment_scope(["FULL_TIME", "PART_TIME"]) == "full_or_part_time"
    assert normalize_employment_scope(["PERMANENT"]) == "unknown"


def test_posting_language_is_observed_context_not_requirement_truth() -> None:
    german = (
        "Wir suchen eine Verstärkung für unser Team. Du arbeitest mit Python und "
        "Machine Learning und übernimmst Verantwortung für unsere Plattform. "
        "Deine Erfahrung und Kenntnisse sind für diese Stelle besonders wichtig."
    )
    english = (
        "We are looking for an engineer for our team. You will work with Python "
        "and machine learning and take responsibility for our platform. Your "
        "experience and skills are important for this role and our application process."
    )

    assert infer_posting_language(german) == "de"
    assert infer_posting_language(english) == "en"
    assert infer_posting_language("Python Kubernetes") == "unknown"


def test_observer_extracts_finanz_informatik_visible_facts_without_contract_guess() -> None:
    text = (
        "Haustarifvertrag. 38 Stunden / Woche. Anteilige mobile Arbeit möglich. "
        "ab 59.417 € / Jahr. Abgeschlossenes Studium sowie mindestens 2-3 Jahre "
        "fachbezogene Berufserfahrung."
    )

    facts = observed_facts_by_field(collect_observed_facts(text))

    assert facts["weekly_hours"][0].value == {"minimum": 38.0, "maximum": 38.0}
    assert facts["work_model"][0].value == "hybrid"
    assert facts["experience"][0].value == {
        "minimum_months": 24,
        "maximum_months": 36,
    }
    assert facts["compensation"][0].value == {
        "amount": 59417.0,
        "currency": "EUR",
        "period": "year",
        "qualifier": "minimum",
    }
    assert facts["collective_agreement_context"][0].value is True


def test_observer_extracts_valuny_fulltime_parenthesized_hours() -> None:
    facts = observed_facts_by_field(
        collect_observed_facts("Wir suchen zum nächstmöglichen Zeitpunkt in Vollzeit (40 h) eine/n AI Consultant.")
    )

    assert facts["weekly_hours"][0].value == {"minimum": 40.0, "maximum": 40.0}


def test_optional_observer_is_discovery_only_and_must_point_to_exact_source_span() -> None:
    class ShadowObserver:
        name = "shadow"

        def observe(self, text: str) -> tuple[ObservedFact, ...]:
            del text
            return (
                ObservedFact(
                    field="shadow_context",
                    value="present",
                    evidence="32 hours per week",
                    basis="external_shadow",
                ),
                ObservedFact(
                    field="compensation",
                    value={"amount": 999999.0},
                    evidence="invented salary",
                    basis="external_shadow",
                ),
            )

    facts = collect_observed_facts(
        "The role is 32 hours per week.",
        optional_observers=(ShadowObserver(),),
    )

    assert any(
        fact.field == "shadow_context" and fact.basis == "external_shadow"
        for fact in facts
    )
    assert all(fact.evidence != "invented salary" for fact in facts)
