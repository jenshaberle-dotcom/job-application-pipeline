"""Build the immutable multi-region company corpus from discovery snapshots."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from src.search_intelligence.connector_mass_census import build_mass_census, seeds_from_payload


def build(paths: list[str]) -> dict[str, object]:
    seeds=[]
    source_files=[]
    for raw in paths:
        path=Path(raw)
        payload=json.loads(path.read_text(encoding="utf-8"))
        source=str(payload.get("source_id") or payload.get("source") or path.stem)
        seeds.extend(seeds_from_payload(payload,default_source=source))
        source_files.append({"path":path.name,"source":source,"records":len(payload.get("companies",[]))})
    result=build_mass_census(seeds,region="MULTI_REGION",experiment_id="cariad-hubs-plus-hannover-social-v1")
    result["source_snapshots"]=sorted(source_files,key=lambda x:(x["source"],x["path"]))
    return result


def main():
    p=argparse.ArgumentParser(); p.add_argument("--seed",action="append",required=True); p.add_argument("--output",required=True)
    a=p.parse_args(); payload=build(a.seed)
    Path(a.output).write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(payload["summary"],sort_keys=True))


if __name__=="__main__": main()
