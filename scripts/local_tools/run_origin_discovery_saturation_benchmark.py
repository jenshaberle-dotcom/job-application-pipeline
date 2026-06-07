from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


CANDIDATES = [
    "technische_informationsbibliothek_tib",
    "ivv",
    "wertgarantie",
    "genoverband_e_v",
    "x1f",
    "materna_information_communications",
    "msg_systems",
    "hannover_ruck",
    "e_on_grid_solutions",
]

TIERS = [
    ("A", 1, 3),
    ("B", 2, 3),
    ("C", 3, 5),
    ("D", 5, 5),
]


@dataclass
class Result:
    tier: str
    company_key: str
    query_limit: int
    max_results: int
    decision: str
    selected_url: str
    search_result_count: int
    selected_domain: str


def run_agent(company_key: str, tier: str, query_limit: int, max_results: int) -> str:
    cmd = [
        "python", "-m", "scripts.run_origin_source_discovery_agent",
        "--company-key", company_key,
        "--target-location", "Hannover",
        "--reviewed-by", f"eo002b_saturation_{tier}",
        "--search-provider", "tavily",
        "--search-query-limit", str(query_limit),
        "--search-max-results", str(max_results),
        "--search-timeout-seconds", "8",
        "--timeout-seconds", "6",
        "--max-candidates", "70",
    ]
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
    return completed.stdout + completed.stderr


def field(text: str, name: str, default: str = "") -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(.*)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else default


def parse_result(tier: str, company_key: str, query_limit: int, max_results: int, text: str) -> Result:
    count_raw = field(text, "search_result_count", "0")
    try:
        count = int(count_raw)
    except ValueError:
        count = 0

    return Result(
        tier=tier,
        company_key=company_key,
        query_limit=query_limit,
        max_results=max_results,
        decision=field(text, "decision", "unknown"),
        selected_url=field(text, "selected_url", ""),
        selected_domain=field(text, "selected_domain", ""),
        search_result_count=count,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="exports/eo002_candidate_flow_benchmark")
    parser.add_argument("--candidate", action="append", dest="candidates")
    parser.add_argument("--tier", action="append", choices=[t[0] for t in TIERS])
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = args.candidates or CANDIDATES
    tiers = [tier for tier in TIERS if not args.tier or tier[0] in args.tier]

    results: list[Result] = []

    for tier, query_limit, max_results in tiers:
        for company_key in candidates:
            print(f"RUN tier={tier} company={company_key} q={query_limit} r={max_results}")
            output = run_agent(company_key, tier, query_limit, max_results)
            safe_name = f"{tier}_{company_key}.txt"
            (out_dir / safe_name).write_text(output, encoding="utf-8")
            results.append(parse_result(tier, company_key, query_limit, max_results, output))

    report = out_dir / "eo002b_origin_discovery_saturation_summary.md"
    lines = [
        "# EO-002B Origin Discovery Saturation Benchmark",
        "",
        "| Tier | Candidate | Queries | Results/query | Search results | Decision | Selected domain | Selected URL |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]

    for r in results:
        lines.append(
            f"| {r.tier} | {r.company_key} | {r.query_limit} | {r.max_results} | "
            f"{r.search_result_count} | {r.decision} | {r.selected_domain or '-'} | {r.selected_url or '-'} |"
        )

    lines.extend([
        "",
        "## Interpretation hints",
        "",
        "- Compare when `selected_url` first appears.",
        "- If higher tiers only add aggregators/noise, the lower tier is the saturation point.",
        "- Track `credits_per_selected_url` manually from tier × candidate count for now.",
    ])

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print()
    print(f"Summary: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
