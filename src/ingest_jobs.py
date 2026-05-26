from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from src.connectors.base import SearchProfile
from src.connectors.bundesagentur import BundesagenturConnector
from src.connectors.greenhouse import GreenhouseConnector
from src.connectors.personio import PersonioConnector
from src.connectors.stepstone import StepStoneConnector
from src.ingestion.repository import JobIngestionRepository
from src.ingestion.runner import JobIngestionRunner


def create_connector(source_name: str):
    if source_name == "bundesagentur_fuer_arbeit":
        return BundesagenturConnector()

    if source_name.startswith("greenhouse:"):
        board_token = source_name.split(":", 1)[1]
        return GreenhouseConnector(board_token=board_token)

    if source_name.startswith("personio:"):
        target_key = source_name.split(":", 1)[1]
        return PersonioConnector(target_key=target_key)

    if source_name == "stepstone":
        return StepStoneConnector()

    raise ValueError(f"No connector configured for source: {source_name}")


def source_matches(source_name: str, source_filter: str) -> bool:
    return source_name == source_filter or source_name.startswith(f"{source_filter}:")


def source_family(source_name: str) -> str:
    return source_name.split(":", 1)[0]


def format_available_profiles(profiles: Sequence[SearchProfile]) -> str:
    if not profiles:
        return "No active profiles are available."

    source_filters = sorted(
        {profile.source_name for profile in profiles}
        | {source_family(profile.source_name) for profile in profiles}
    )

    lines = ["Available active profiles:"]

    for profile in profiles:
        lines.append(
            f"- {profile.profile_name} "
            f"(source={profile.source_name}, family={source_family(profile.source_name)})"
        )

    lines.append("")
    lines.append("Available source filters:")

    for source_filter in source_filters:
        lines.append(f"- {source_filter}")

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run job ingestion for all active profiles, a source family, or one profile."
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--profile",
        help="Run exactly one active search profile by profile name.",
    )
    mode.add_argument(
        "--source",
        help="Run all active profiles for one source family, e.g. greenhouse.",
    )
    mode.add_argument(
        "--list-profiles",
        action="store_true",
        help="List active search profiles and terms without running ingestion.",
    )

    parser.add_argument(
        "legacy_profile_name",
        nargs="?",
        help=argparse.SUPPRESS,
    )

    return parser


def normalize_arguments(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> argparse.Namespace:
    if args.legacy_profile_name:
        if args.profile or args.source or args.list_profiles:
            parser.error("Do not combine positional profile names with --profile, --source or --list-profiles.")

        args.profile = args.legacy_profile_name

    return args


def select_profiles(
    repository: JobIngestionRepository,
    profile_name: str | None,
    source_filter: str | None,
) -> list[SearchProfile]:
    profiles = repository.load_active_search_profiles()

    if profile_name:
        selected_profiles = [
            profile
            for profile in profiles
            if profile.profile_name == profile_name
        ]

        if selected_profiles:
            return selected_profiles

        raise ValueError(
            f"No active search profile found: {profile_name}\n\n"
            f"{format_available_profiles(profiles)}"
        )

    if source_filter:
        selected_profiles = [
            profile
            for profile in profiles
            if source_matches(
                source_name=profile.source_name,
                source_filter=source_filter,
            )
        ]

        if selected_profiles:
            return selected_profiles

        raise ValueError(
            f"No active search profiles found for source: {source_filter}\n\n"
            f"{format_available_profiles(profiles)}"
        )

    if not profiles:
        raise ValueError("No active search profiles found.")

    return profiles


def print_profiles(repository: JobIngestionRepository) -> None:
    profiles = repository.load_active_search_profiles()

    print()
    print("=== Active Search Profiles ===")
    print()

    for profile in profiles:
        print(
            f"[{profile.id}] {profile.profile_name} "
            f"source={profile.source_name} "
            f"location={profile.search_location} "
            f"radius_km={profile.search_radius_km}"
        )

        terms = repository.load_active_search_terms(profile.profile_name)

        if not terms:
            print("    - no active search terms")
            continue

        for _, search_term in terms:
            term_id = search_term.id if search_term.id is not None else "?"
            print(f"    - [{term_id}] {search_term.search_term}")


def run_profile(
    repository: JobIngestionRepository,
    profile: SearchProfile,
) -> None:
    connector = create_connector(source_name=profile.source_name)

    runner = JobIngestionRunner(
        repository=repository,
        connector=connector,
    )

    runner.run(profile_name=profile.profile_name)


def run_profiles(
    repository: JobIngestionRepository,
    profiles: Sequence[SearchProfile],
) -> int:
    failed_profiles: list[tuple[str, Exception]] = []

    for profile in profiles:
        print("===")
        print(f"Running ingestion profile: {profile.profile_name}")
        print(f"Source: {profile.source_name}")

        try:
            run_profile(
                repository=repository,
                profile=profile,
            )
        except Exception as exc:
            failed_profiles.append((profile.profile_name, exc))
            print(
                f"Failed ingestion profile {profile.profile_name}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    if failed_profiles:
        print("===")
        print("Failed ingestion profiles:", file=sys.stderr)

        for profile_name, exc in failed_profiles:
            print(
                f"- {profile_name}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

        return 1

    return 0


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = normalize_arguments(
        parser=parser,
        args=parser.parse_args(argv),
    )

    repository = JobIngestionRepository()

    if args.list_profiles:
        print_profiles(repository)
        return

    try:
        profiles = select_profiles(
            repository=repository,
            profile_name=args.profile,
            source_filter=args.source,
        )
    except ValueError as exc:
        parser.exit(
            status=2,
            message=f"Error: {exc}\n\nHint: python -m src.ingest_jobs --list-profiles\n",
        )

    exit_code = run_profiles(
        repository=repository,
        profiles=profiles,
    )

    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
