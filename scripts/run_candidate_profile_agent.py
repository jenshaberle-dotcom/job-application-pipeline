from __future__ import annotations

import argparse
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.candidate_intelligence import (
    DEFAULT_PROFILE,
    DEFAULT_SKILLS,
    CandidateProfileSeed,
    CandidateSkill,
    profile_summary,
)


class DatabaseConfig:
    @classmethod
    def dsn(cls) -> str:
        return (
            f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
            f"port={os.environ.get('POSTGRES_PORT', '5432')} "
            f"dbname={os.environ['POSTGRES_DB']} "
            f"user={os.environ['POSTGRES_USER']} "
            f"password={os.environ['POSTGRES_PASSWORD']}"
        )


def upsert_profile(conn: psycopg.Connection[Any], profile: CandidateProfileSeed) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            insert into candidate_profiles (
                profile_name,
                target_role,
                profile_version,
                notes,
                updated_at
            ) values (%s, %s, %s, %s, now())
            on conflict (profile_name, profile_version)
            do update set
                target_role = excluded.target_role,
                notes = excluded.notes,
                updated_at = now()
            returning id
            """,
            (profile.profile_name, profile.target_role, profile.profile_version, profile.notes),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("candidate profile upsert did not return an id")
    return int(row["id"])


def upsert_skills(conn: psycopg.Connection[Any], *, candidate_profile_id: int, skills: tuple[CandidateSkill, ...]) -> int:
    count = 0
    with conn.cursor() as cur:
        for skill in skills:
            cur.execute(
                """
                insert into candidate_skills (
                    candidate_profile_id,
                    skill_name,
                    skill_category,
                    capability_score,
                    career_direction_weight,
                    notes,
                    updated_at
                ) values (%s, %s, %s, %s, %s, %s, now())
                on conflict (candidate_profile_id, skill_name)
                do update set
                    skill_category = excluded.skill_category,
                    capability_score = excluded.capability_score,
                    career_direction_weight = excluded.career_direction_weight,
                    notes = excluded.notes,
                    updated_at = now()
                """,
                (
                    candidate_profile_id,
                    skill.skill_name,
                    skill.skill_category,
                    skill.capability_score,
                    skill.career_direction_weight,
                    skill.notes,
                ),
            )
            count += 1
    return count


def load_profile_skills(conn: psycopg.Connection[Any], *, profile_name: str, profile_version: str) -> tuple[CandidateProfileSeed, tuple[CandidateSkill, ...]] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                id,
                profile_name,
                target_role,
                profile_version,
                notes
            from candidate_profiles
            where profile_name = %s
              and profile_version = %s
            """,
            (profile_name, profile_version),
        )
        profile_row = cur.fetchone()
        if profile_row is None:
            return None

        cur.execute(
            """
            select
                skill_name,
                skill_category,
                capability_score,
                career_direction_weight,
                notes
            from candidate_skills
            where candidate_profile_id = %s
            order by career_direction_weight desc, capability_score desc, skill_name
            """,
            (profile_row["id"],),
        )
        skill_rows = cur.fetchall()

    return (
        CandidateProfileSeed(
            profile_name=str(profile_row["profile_name"]),
            target_role=str(profile_row["target_role"]),
            profile_version=str(profile_row["profile_version"]),
            notes=str(profile_row["notes"] or ""),
        ),
        tuple(
            CandidateSkill(
                skill_name=str(row["skill_name"]),
                skill_category=str(row["skill_category"]),
                capability_score=int(row["capability_score"]),
                career_direction_weight=int(row["career_direction_weight"]),
                notes=str(row["notes"] or ""),
            )
            for row in skill_rows
        ),
    )


def print_summary(profile: CandidateProfileSeed, skills: tuple[CandidateSkill, ...], *, write_mode: bool) -> None:
    summary = profile_summary(skills)
    print("Candidate Intelligence Preview")
    print(f"profile_name: {profile.profile_name}")
    print(f"target_role: {profile.target_role}")
    print(f"profile_version: {profile.profile_version}")
    print(f"skill_count: {len(skills)}")
    print("---")
    print("top_strengths:")
    for skill in summary["strengths"]:
        print(f"- {skill.skill_name}: capability={skill.capability_score} direction={skill.career_direction_weight}")
    print("---")
    print("transition_assets:")
    for skill in summary["transition_assets"]:
        print(f"- {skill.skill_name}: capability={skill.capability_score} direction={skill.career_direction_weight}")
    print("---")
    print("growth_areas:")
    for skill in summary["growth_areas"]:
        print(f"- {skill.skill_name}: capability={skill.capability_score} direction={skill.career_direction_weight} gap={skill.growth_gap}")
    print("---")
    print(f"write_mode: {str(write_mode).lower()}")
    if not write_mode:
        print("NEXT: rerun with --write after reviewing the candidate profile seed.")


def run(args: argparse.Namespace) -> int:
    profile = DEFAULT_PROFILE
    skills = DEFAULT_SKILLS

    if args.write:
        with psycopg.connect(DatabaseConfig.dsn()) as conn:
            profile_id = upsert_profile(conn, profile)
            skill_count = upsert_skills(conn, candidate_profile_id=profile_id, skills=skills)
            conn.commit()
            loaded = load_profile_skills(
                conn,
                profile_name=profile.profile_name,
                profile_version=profile.profile_version,
            )
            if loaded is not None:
                profile, skills = loaded

        print_summary(profile, skills, write_mode=True)
        print(f"candidate_profile_upsert_count: 1")
        print(f"candidate_skill_upsert_count: {skill_count}")
        print("boundary: no search-profile mutation, no source activation, no Bronze write, no scheduler change")
        return 0

    print_summary(profile, skills, write_mode=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview or seed the candidate intelligence profile.")
    parser.add_argument("--write", action="store_true", help="Persist the default candidate profile and skills.")
    parser.add_argument("--reviewed-by", default="unknown", help="Review marker for operator traceability; currently printed only.")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
