"""Materialize stable ML examples from census + Factory evaluation."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

LABELS={
 "qualified_inactive":"SUCCESS",
 "evidence_gap":"EVIDENCE_GAP",
 "capability_gap":"CAPABILITY_GAP",
 "runtime_gap":"RUNTIME_GAP",
 "qualification_gap":"QUALIFICATION_GAP",
}


def materialize(census,evaluation):
    companies={str(x["company_key"]):x for x in census.get("candidates",[])}
    examples=[]
    for row in evaluation.get("candidates",[]):
        key=str(row["company_key"]); company=companies[key]
        disposition=str(row.get("factory_disposition",""))
        label=LABELS.get(disposition,"EXTRACTION_FAILURE")
        payload={
          "company_key":key,
          "geographies":company.get("geographies",[]),
          "cohorts":company.get("cohorts",[]),
          "source_lineage":company.get("seed_sources",[]),
          "origin_url":row.get("origin_url"),
          "fingerprint_tags":row.get("fingerprint_tags",[]),
          "capability_ids":row.get("capability_ids",[]),
          "factory_disposition":disposition,
          "extraction_field_presence":{},
          "job_count":0,
          "failure_fingerprint":(row.get("engineering_gap") or {}).get("fingerprint"),
          "label":label,
          "raw_capture_digest":None,
          "raw_capture_persisted":False,
        }
        payload["example_id"]=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        examples.append(payload)
    examples.sort(key=lambda x:x["example_id"])
    counts={}
    for row in examples: counts[row["label"]]=counts.get(row["label"],0)+1
    return {"schema_version":"jap.connector_ml_corpus.v1","population_digest":census["population_digest"],
            "example_count":len(examples),"label_counts":dict(sorted(counts.items())),"examples":examples}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--census",required=True); p.add_argument("--evaluation",required=True); p.add_argument("--output",required=True)
    a=p.parse_args(); load=lambda x:json.loads(Path(x).read_text(encoding="utf-8"))
    result=materialize(load(a.census),load(a.evaluation))
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"examples":result["example_count"],"labels":result["label_counts"]},sort_keys=True))


if __name__=="__main__": main()
