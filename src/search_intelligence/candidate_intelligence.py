from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateProfileSeed:
    profile_name: str
    target_role: str
    profile_version: str
    notes: str


@dataclass(frozen=True)
class CandidateSkill:
    skill_name: str
    skill_category: str
    capability_score: int
    career_direction_weight: int
    notes: str = ""

    @property
    def growth_gap(self) -> int:
        return max(0, self.career_direction_weight - self.capability_score)


DEFAULT_PROFILE = CandidateProfileSeed(
    profile_name="Jens Career Transition",
    target_role="Data Engineer",
    profile_version="v1",
    notes=(
        "Initial manually curated profile for the job-application-pipeline. "
        "It separates current capability from desired career direction."
    ),
)


DEFAULT_SKILLS: tuple[CandidateSkill, ...] = (
    CandidateSkill("Requirements Engineering", "requirements", 95, 25, "Strong current capability, lower target direction."),
    CandidateSkill("Systems Engineering", "architecture", 90, 30, "Strong current capability from automotive systems context."),
    CandidateSkill("Product Ownership", "product", 90, 40, "Strong capability; valuable mainly in data-product contexts."),
    CandidateSkill("Stakeholder Management", "product", 90, 55, "Transferable strength."),
    CandidateSkill("Automotive Domain", "domain", 85, 45, "Useful domain background but not the target role itself."),
    CandidateSkill("SQL", "data_engineering", 75, 100, "Core data-engineering skill."),
    CandidateSkill("Python", "programming", 70, 100, "Core data-engineering skill."),
    CandidateSkill("PostgreSQL", "data_engineering", 70, 95, "Core project and data-modeling skill."),
    CandidateSkill("Data Modeling", "data_engineering", 65, 95, "Important for Bronze/Silver/Gold modeling."),
    CandidateSkill("ETL Pipelines", "data_engineering", 60, 100, "Core direction for the portfolio project."),
    CandidateSkill("Azure", "cloud", 60, 95, "Relevant cloud direction with existing exposure."),
    CandidateSkill("Git", "engineering_practice", 70, 85, "Important engineering practice."),
    CandidateSkill("CI/CD", "engineering_practice", 60, 80, "Relevant engineering practice."),
    CandidateSkill("Analytics", "analytics", 60, 95, "Strong target signal from recent market evidence."),
    CandidateSkill("Business Intelligence", "analytics", 55, 75, "Adjacent useful analytics skill."),
    CandidateSkill("Databricks", "data_engineering", 20, 100, "High-priority growth skill."),
    CandidateSkill("Spark", "data_engineering", 15, 100, "High-priority growth skill."),
    CandidateSkill("Kafka", "data_engineering", 10, 95, "Strategic growth skill; useful for streaming roles."),
    CandidateSkill("Cloud Data Platforms", "cloud", 35, 95, "Growth area for target role."),
    CandidateSkill("Machine Learning", "analytics", 35, 65, "Relevant but not the primary target."),
    CandidateSkill("Scrum", "agile", 85, 45, "Strong capability, secondary target direction."),
    CandidateSkill("SAFe", "agile", 65, 35, "Context skill, not a primary target direction."),
)


def validate_score(value: int, *, field_name: str) -> int:
    if not 0 <= value <= 100:
        raise ValueError(f"{field_name} must be between 0 and 100")
    return value


def validate_skill(skill: CandidateSkill) -> CandidateSkill:
    if not skill.skill_name.strip():
        raise ValueError("skill_name must not be empty")
    if not skill.skill_category.strip():
        raise ValueError("skill_category must not be empty")
    validate_score(skill.capability_score, field_name="capability_score")
    validate_score(skill.career_direction_weight, field_name="career_direction_weight")
    return skill


def top_strengths(skills: list[CandidateSkill] | tuple[CandidateSkill, ...], *, limit: int = 5) -> list[CandidateSkill]:
    return sorted(
        (validate_skill(skill) for skill in skills),
        key=lambda skill: (skill.capability_score, skill.career_direction_weight, skill.skill_name.lower()),
        reverse=True,
    )[:limit]


def top_growth_areas(skills: list[CandidateSkill] | tuple[CandidateSkill, ...], *, limit: int = 5) -> list[CandidateSkill]:
    candidates = [validate_skill(skill) for skill in skills if skill.career_direction_weight >= 70 and skill.growth_gap > 0]
    return sorted(
        candidates,
        key=lambda skill: (skill.growth_gap, skill.career_direction_weight, -skill.capability_score, skill.skill_name.lower()),
        reverse=True,
    )[:limit]


def transition_assets(skills: list[CandidateSkill] | tuple[CandidateSkill, ...], *, limit: int = 5) -> list[CandidateSkill]:
    candidates = [validate_skill(skill) for skill in skills if skill.capability_score >= 60 and skill.career_direction_weight >= 75]
    return sorted(
        candidates,
        key=lambda skill: (skill.career_direction_weight, skill.capability_score, skill.skill_name.lower()),
        reverse=True,
    )[:limit]


def profile_summary(skills: list[CandidateSkill] | tuple[CandidateSkill, ...]) -> dict[str, list[CandidateSkill]]:
    return {
        "strengths": top_strengths(skills),
        "transition_assets": transition_assets(skills),
        "growth_areas": top_growth_areas(skills),
    }
