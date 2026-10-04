"""Config-driven discovery for public HTML employer directories."""
from __future__ import annotations
import argparse, json, re, time
from pathlib import Path
from urllib.parse import urlparse
from src.search_intelligence.public_directory_discovery import DirectorySource, fetch_text, links, seed


def discover(config: dict[str, object]) -> dict[str, object]:
    source=DirectorySource(
        str(config["source_id"]),str(config["geography"]),tuple(config.get("cohorts",["TECH"])),
        str(config["start_url"]),int(config.get("max_pages",100)))
    include=tuple(str(x).casefold() for x in config.get("include_href",[]))
    exclude=tuple(str(x).casefold() for x in config.get("exclude_href",[]))
    next_template=config.get("page_url_template")
    companies={}
    empty=0
    for page in range(1,source.max_pages+1):
        url=str(next_template).format(page=page) if next_template else source.start_url
        html=fetch_text(url)
        count=0
        for href,text in links(html,url):
            h=href.casefold(); name=" ".join(text.split())
            if include and not any(token in h for token in include): continue
            if exclude and any(token in h for token in exclude): continue
            if len(name)<2 or len(name)>180: continue
            key=href.split("?",1)[0].rstrip("/")
            if key==source.start_url.rstrip("/"): continue
            companies.setdefault(key,seed(name,source,website=key,source_record_id=key)); count+=1
        empty=empty+1 if count==0 else 0
        if not next_template or empty>=2: break
        time.sleep(float(config.get("delay_seconds",.2)))
    return {"schema_version":"jap.discovery.configured_html.v1","source_id":source.source_id,
            "geography":source.geography,"company_count":len(companies),
            "companies":sorted(companies.values(),key=lambda x:str(x["company_name"]).casefold())}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--config",required=True); p.add_argument("--output",required=True); a=p.parse_args()
    result=discover(json.loads(Path(a.config).read_text(encoding="utf-8")))
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"source":result["source_id"],"companies":result["company_count"]},sort_keys=True))


if __name__=="__main__": main()
