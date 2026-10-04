"""Bridge immutable company census + acquired origin evidence into aggressive Factory evaluation."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from src.connectors.aggressive_factory import advance_population


def evaluate(census: dict[str, object], evidence: dict[str, object], catalog: dict[str, object]) -> dict[str, object]:
    by_key={str(row["company_key"]):row for row in evidence.get("candidates",[])}
    sources=[]
    missing=[]
    for company in census.get("candidates",[]):
        key=str(company["company_key"])
        row=by_key.get(key)
        if row is None:
            missing.append(key)
            sources.append({"company_key":key,"evidence_ids":[],"fingerprint_tags":[]})
        else:
            sources.append(row)
    result=advance_population(sources,catalog_payload=catalog,census_digest=str(census["population_digest"]))
    result["population_digest"]=census["population_digest"]
    result["origin_evidence_coverage"]={
        "population":len(census.get("candidates",[])),
        "with_evidence":len(census.get("candidates",[]))-len(missing),
        "missing_evidence":len(missing),
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--census",required=True); p.add_argument("--evidence",required=True)
    p.add_argument("--catalog",default="contracts/connector-capability-catalog-v1.json"); p.add_argument("--output",required=True)
    a=p.parse_args()
    load=lambda x: json.loads(Path(x).read_text(encoding="utf-8"))
    result=evaluate(load(a.census),load(a.evidence),load(a.catalog))
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"dispositions":result["disposition_counts"],"coverage":result["origin_evidence_coverage"]},sort_keys=True))


if __name__=="__main__": main()
