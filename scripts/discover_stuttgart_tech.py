"""Region Stuttgart technology-company discovery adapter."""
from __future__ import annotations
import argparse, json
from src.search_intelligence.public_directory_discovery import DirectorySource, fetch_text, links, seed

SOURCE = DirectorySource(
    source_id="region_stuttgart_technology_directory",
    geography="STUTTGART_REGION",
    cohorts=("TECH",),
    start_url="https://www.region-stuttgart.de/type/unternehmen/",
)
TECH_HINTS=("unternehmen","robot","sensor","quant","halbleiter","photon")


def discover() -> dict[str, object]:
    html=fetch_text(SOURCE.start_url)
    companies={}
    for href,text in links(html,SOURCE.start_url):
        normalized=" ".join(text.split())
        if len(normalized)<2 or normalized.casefold() in {"alle","reset","suche"}:
            continue
        if "/unternehmen/" not in href.rstrip("/").casefold():
            continue
        key=href.split("?",1)[0].rstrip("/")
        if key == SOURCE.start_url.rstrip("/"):
            continue
        companies.setdefault(key,seed(normalized,SOURCE,website=key,source_record_id=key))
    return {"schema_version":"jap.discovery.region_stuttgart_technology.v1","source_id":SOURCE.source_id,
            "geography":SOURCE.geography,"company_count":len(companies),
            "companies":sorted(companies.values(),key=lambda x:str(x["company_name"]).casefold())}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--output",required=True); a=p.parse_args(); payload=discover()
    with open(a.output,"w",encoding="utf-8") as h: json.dump(payload,h,ensure_ascii=False,indent=2,sort_keys=True); h.write("\n")
    print(json.dumps({"source":SOURCE.source_id,"companies":payload["company_count"]}))


if __name__=="__main__": main()
