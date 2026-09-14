# Exact-head requalification marker for the R4 v1.0.29 operator release.
from src.silver.operator_requirement_semantics import (
    infer_posting_language,
    normalize_employment_scope,
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
