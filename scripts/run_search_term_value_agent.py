from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.candidate_intelligence import CandidateProfileSeed, CandidateSkill, DEFAULT_PROFILE
from src.search_intelligence.search_term_value import (
    SearchTermValueScore,
    VocabularySignalInput,
    VocabularySignalScore,
    build_search_term_value_scores,
    build_vocabulary_signal_scores,
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


def load_vocabulary_inputs(conn: psycopg.Connection[Any], *, limit: int) -> list[VocabularySignalInput]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                observed_term,
                count(distinct company_key)::int as company_count,
                coalesce(sum(observation_count), 0)::int as observation_count
            from company_vocabulary_observations
            group by observed_term
            order by observation_count desc, company_count desc, observed_term
            limit %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [
        VocabularySignalInput(
            observed_term=str(row["observed_term"]),
            company_count=int(row["company_count"] or 0),
            observation_count=int(row["observation_count"] or 0),
        )
        for row in rows
    ]


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


def write_vocabulary_signal_scores(
    conn: psycopg.Connection[Any],
    *,
    scores: list[VocabularySignalScore],
    reviewed_by: str,
) -> int:
    count = 0
    with conn.cursor() as cur:
        for item in scores:
            cur.execute(
                """
                insert into vocabulary_signal_scores (
                    observed_term,
                    company_count,
                    observation_count,
                    noise_penalty,
                    signal_score,
                    evidence,
                    reviewed_by,
                    updated_at
                ) values (%s, %s, %s, %s, %s, %s::jsonb, %s, now())
                on conflict (observed_term)
                do update set
                    company_count = excluded.company_count,
                    observation_count = excluded.observation_count,
                    noise_penalty = excluded.noise_penalty,
                    signal_score = excluded.signal_score,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by,
                    updated_at = now()
                """,
                (
                    item.observed_term,
                    item.company_count,
                    item.observation_count,
                    item.noise_penalty,
                    item.signal_score,
                    json.dumps(asdict(item), default=str),
                    reviewed_by,
                ),
            )
            count += 1
    return count


def write_search_term_value_scores(
    conn: psycopg.Connection[Any],
    *,
    scores: list[SearchTermValueScore],
    reviewed_by: str,
) -> int:
    count = 0
    with conn.cursor() as cur:
        for item in scores:
            cur.execute(
                """
                insert into search_term_value_scores (
                    observed_term,
                    profile_name,
                    profile_version,
                    matched_skill_name,
                    matched_skill_category,
                    vocabulary_signal_score,
                    career_direction_score,
                    capability_alignment_score,
                    growth_gap_score,
                    overall_value_score,
                    value_band,
                    evidence,
                    reviewed_by,
                    updated_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, now())
                on conflict (observed_term, profile_name, profile_version)
                do update set
                    matched_skill_name = excluded.matched_skill_name,
                    matched_skill_category = excluded.matched_skill_category,
                    vocabulary_signal_score = excluded.vocabulary_signal_score,
                    career_direction_score = excluded.career_direction_score,
                    capability_alignment_score = excluded.capability_alignment_score,
                    growth_gap_score = excluded.growth_gap_score,
                    overall_value_score = excluded.overall_value_score,
                    value_band = excluded.value_band,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by,
                    updated_at = now()
                """,
                (
                    item.observed_term,
                    item.profile_name,
                    item.profile_version,
                    item.matched_skill_name,
                    item.matched_skill_category,
                    item.vocabulary_signal_score,
                    item.career_direction_score,
                    item.capability_alignment_score,
                    item.growth_gap_score,
                    item.overall_value_score,
                    item.value_band,
                    json.dumps(asdict(item), default=str),
                    reviewed_by,
                ),
            )
            count += 1
    return count


def print_preview(
    *,
    vocabulary_scores: list[VocabularySignalScore],
    value_scores: list[SearchTermValueScore],
    write: bool,
) -> None:
    print("Search-Term Value Preview")
    print(f"vocabulary_signal_count: {len(vocabulary_scores)}")
    print(f"search_term_value_count: {len(value_scores)}")
    print("---")
    for item in value_scores[:15]:
        matched = item.matched_skill_name or "unmatched"
        print(
            f"term: {item.observed_term} | value: {item.overall_value_score} | "
            f"band: {item.value_band} | signal: {item.vocabulary_signal_score} | "
            f"career: {item.career_direction_score} | capability: {item.capability_alignment_score} | "
            f"skill: {matched}"
        )
    print("---")
    print(f"write_mode: {str(write).lower()}")
    if not write:
        print("NEXT: rerun with --write after reviewing search-term value scores.")


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        profile, skills = load_candidate_profile_and_skills(
            conn,
            profile_name=args.profile_name,
            profile_version=args.profile_version,
        )
        vocabulary_scores = build_vocabulary_signal_scores(load_vocabulary_inputs(conn, limit=args.limit))
        value_scores = build_search_term_value_scores(
            vocabulary_scores,
            profile_name=profile.profile_name,
            profile_version=profile.profile_version,
            skills=skills,
        )
        print_preview(vocabulary_scores=vocabulary_scores, value_scores=value_scores, write=args.write)
        if args.write:
            signal_count = write_vocabulary_signal_scores(conn, scores=vocabulary_scores, reviewed_by=args.reviewed_by)
            value_count = write_search_term_value_scores(conn, scores=value_scores, reviewed_by=args.reviewed_by)
            conn.commit()
            print(f"vocabulary_signal_score_upsert_count: {signal_count}")
            print(f"search_term_value_score_upsert_count: {value_count}")
            print("boundary: no search-profile mutation, no source activation, no Bronze write, no scheduler change")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score observed vocabulary and candidate-specific search-term value.")
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
