from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.candidate_intelligence import CandidateProfileSeed, CandidateSkill, DEFAULT_PROFILE
from src.search_intelligence.capability_gap import CapabilityGapScore, SearchTermSupport, build_capability_gap_scores


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


def load_candidate_profile_and_skills(
    conn: psycopg.Connection[Any],
    *,
    profile_name: str,
    profile_version: str,
) -> tuple[CandidateProfileSeed, list[CandidateSkill]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select id, profile_name, target_role, profile_version, notes
            from candidate_profiles
            where profile_name = %s and profile_version = %s
            """,
            (profile_name, profile_version),
        )
        profile_row = cur.fetchone()
        if profile_row is None:
            raise RuntimeError(
                f"candidate profile {profile_name!r} / {profile_version!r} not found. "
                "Run scripts.run_candidate_profile_agent --write first."
            )
        cur.execute(
            """
            select skill_name, skill_category, capability_score, career_direction_weight, coalesce(notes, '') as notes
            from candidate_skills
            where candidate_profile_id = %s
            order by skill_name
            """,
            (profile_row["id"],),
        )
        skill_rows = cur.fetchall()

    profile = CandidateProfileSeed(
        profile_name=str(profile_row["profile_name"]),
        target_role=str(profile_row["target_role"]),
        profile_version=str(profile_row["profile_version"]),
        notes=str(profile_row["notes"] or ""),
    )
    skills = [
        CandidateSkill(
            skill_name=str(row["skill_name"]),
            skill_category=str(row["skill_category"]),
            capability_score=int(row["capability_score"]),
            career_direction_weight=int(row["career_direction_weight"]),
            notes=str(row["notes"] or ""),
        )
        for row in skill_rows
    ]
    return profile, skills


def load_term_supports(
    conn: psycopg.Connection[Any],
    *,
    profile_name: str,
    profile_version: str,
    limit: int,
) -> list[SearchTermSupport]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                observed_term,
                matched_skill_name,
                overall_value_score,
                value_band
            from search_term_value_scores
            where profile_name = %s
              and profile_version = %s
              and matched_skill_name is not null
            order by overall_value_score desc, observed_term
            limit %s
            """,
            (profile_name, profile_version, limit),
        )
        rows = cur.fetchall()

    return [
        SearchTermSupport(
            observed_term=str(row["observed_term"]),
            matched_skill_name=str(row["matched_skill_name"]),
            overall_value_score=row["overall_value_score"],
            value_band=str(row["value_band"]),
        )
        for row in rows
    ]


def write_capability_gap_scores(
    conn: psycopg.Connection[Any],
    *,
    scores: list[CapabilityGapScore],
    reviewed_by: str,
) -> int:
    count = 0
    with conn.cursor() as cur:
        for item in scores:
            cur.execute(
                """
                insert into capability_gap_scores (
                    profile_name,
                    profile_version,
                    skill_name,
                    skill_category,
                    capability_score,
                    career_direction_weight,
                    growth_gap,
                    supporting_term_count,
                    supporting_terms,
                    max_search_term_value,
                    avg_search_term_value,
                    market_signal_score,
                    priority_score,
                    priority_band,
                    recommendation,
                    evidence,
                    reviewed_by,
                    updated_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, now())
                on conflict (profile_name, profile_version, skill_name)
                do update set
                    skill_category = excluded.skill_category,
                    capability_score = excluded.capability_score,
                    career_direction_weight = excluded.career_direction_weight,
                    growth_gap = excluded.growth_gap,
                    supporting_term_count = excluded.supporting_term_count,
                    supporting_terms = excluded.supporting_terms,
                    max_search_term_value = excluded.max_search_term_value,
                    avg_search_term_value = excluded.avg_search_term_value,
                    market_signal_score = excluded.market_signal_score,
                    priority_score = excluded.priority_score,
                    priority_band = excluded.priority_band,
                    recommendation = excluded.recommendation,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by,
                    updated_at = now()
                """,
                (
                    item.profile_name,
                    item.profile_version,
                    item.skill_name,
                    item.skill_category,
                    item.capability_score,
                    item.career_direction_weight,
                    item.growth_gap,
                    len(item.supporting_terms),
                    json.dumps(list(item.supporting_terms), default=str),
                    item.max_search_term_value,
                    item.avg_search_term_value,
                    item.market_signal_score,
                    item.priority_score,
                    item.priority_band,
                    item.recommendation,
                    json.dumps(asdict(item), default=str),
                    reviewed_by,
                ),
            )
            count += 1
    return count


def print_preview(*, profile: CandidateProfileSeed, scores: list[CapabilityGapScore], write: bool) -> None:
    print("Capability Gap Preview")
    print(f"profile_name: {profile.profile_name}")
    print(f"target_role: {profile.target_role}")
    print(f"capability_gap_count: {len(scores)}")
    print("---")
    for item in scores[:15]:
        terms = ", ".join(item.supporting_terms) if item.supporting_terms else "-"
        print(
            f"skill: {item.skill_name} | priority: {item.priority_score} | "
            f"band: {item.priority_band} | recommendation: {item.recommendation} | "
            f"gap: {item.growth_gap} | market: {item.market_signal_score} | terms: {terms}"
        )
    print("---")
    print(f"write_mode: {str(write).lower()}")
    if not write:
        print("NEXT: rerun with --write after reviewing capability gap priorities.")


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        profile, skills = load_candidate_profile_and_skills(
            conn,
            profile_name=args.profile_name,
            profile_version=args.profile_version,
        )
        supports = load_term_supports(
            conn,
            profile_name=profile.profile_name,
            profile_version=profile.profile_version,
            limit=args.limit,
        )
        scores = build_capability_gap_scores(
            profile_name=profile.profile_name,
            profile_version=profile.profile_version,
            skills=skills,
            term_supports=supports,
        )
        print_preview(profile=profile, scores=scores, write=args.write)
        if args.write:
            count = write_capability_gap_scores(conn, scores=scores, reviewed_by=args.reviewed_by)
            conn.commit()
            print(f"capability_gap_score_upsert_count: {count}")
            print("boundary: no search-profile mutation, no source activation, no Bronze write, no scheduler change")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build candidate capability-gap priorities from search-term value signals.")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--profile-name", default=DEFAULT_PROFILE.profile_name)
    parser.add_argument("--profile-version", default=DEFAULT_PROFILE.profile_version)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--reviewed-by", default="agent")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
