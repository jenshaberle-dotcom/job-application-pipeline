from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_doc001n_engineering_principles_current_truth_exists() -> None:
    doc = read("docs/current/engineering_principles.md")

    required_terms = [
        "Keep it simple, but reliable",
        "Explicit Ownership",
        "Human Oversight",
        "Fail Closed",
        "Documentation as Operational Contract",
        "Sustainable Engineering",
        "Compliance Readiness",
        "Quality attributes",
        "governance monsters",
        "compliance monsters",
        "documentation monsters",
    ]

    for term in required_terms:
        assert term in doc


def test_doc001n_is_linked_from_documentation_and_governance_current_truth() -> None:
    docs_readme = read("docs/README.md")
    governance = read("docs/current/governance.md")

    assert "current/engineering_principles.md" in docs_readme
    assert "engineering_principles.md" in governance


def test_doc001n_keeps_compliance_as_pragmatic_readiness_not_certification() -> None:
    doc = read("docs/current/engineering_principles.md")

    assert "does not simulate formal certification" in doc
    assert "without compliance theatre" in doc
    assert "Controls should exist because they reduce real engineering risk" in doc
