"""Run all configured company discovery providers and build one immutable corpus."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

CONFIGS=(
 "contracts/discovery/berlin-startup-map.json",
 "contracts/discovery/wolfsburg-innovations.json",
 "contracts/discovery/ingolstadt-digital.json",
)


def run(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True,exist_ok=True)
    snapshots=[]
    commands=[
      [sys.executable,"scripts/discover_hannover_tech_hsh.py","--output",str(output_dir/"hannover-hsh.json")],
      [sys.executable,"scripts/discover_munich_startups.py","--output",str(output_dir/"munich-startups.json")],
      [sys.executable,"scripts/discover_stuttgart_tech.py","--output",str(output_dir/"stuttgart-tech.json")],
    ]
    snapshots.extend([output_dir/"hannover-hsh.json",output_dir/"munich-startups.json",output_dir/"stuttgart-tech.json"])
    for config in CONFIGS:
        name=Path(config).stem+".json"; target=output_dir/name
        commands.append([sys.executable,"scripts/discover_configured_directory.py","--config",config,"--output",str(target)])
        snapshots.append(target)
    for command in commands: subprocess.run(command,check=True)
    census=output_dir/"multi-region-company-census.json"
    command=[sys.executable,"scripts/build_connector_ml_corpus.py"]
    for snapshot in snapshots: command.extend(["--seed",str(snapshot)])
    command.extend(["--output",str(census)])
    subprocess.run(command,check=True)
    return census


def main():
    p=argparse.ArgumentParser(); p.add_argument("--output-dir",default="artifacts/connector-corpus"); a=p.parse_args()
    census=run(Path(a.output_dir)); print(json.dumps({"census":str(census)},sort_keys=True))


if __name__=="__main__": main()
