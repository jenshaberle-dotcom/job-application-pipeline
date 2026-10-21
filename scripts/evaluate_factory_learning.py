"""Read-only, identity-stable evaluation of two completed RCC Census campaigns."""
import argparse
import json
from pathlib import Path
from scripts.run_native_census_campaign import connect
from src.search_intelligence.factory_learning import evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with connect() as db:
        db.execute("SET TRANSACTION READ ONLY")
        def rows(run):
            data = db.execute("""SELECT c.observation,f.state,f.result
                FROM bronze_native_census_candidates c LEFT JOIN native_census_factory_results f
                ON c.id=f.candidate_id WHERE c.run_id=%s ORDER BY c.company_key""", (run,)).fetchall()
            if not data or any(r[1] in (None, "ASSESSING") for r in data):
                raise ValueError("CAMPAIGN_NOT_COMPLETE")
            return data
        report = evaluate(rows(args.current), rows(args.previous))
    report.update(current_run=args.current, previous_run=args.previous, effects=False)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "cohorts"}))


if __name__ == "__main__":
    main()
