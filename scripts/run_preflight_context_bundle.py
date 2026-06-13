from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.preflight_context_support import create_context_bundle  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a robust preflight context ZIP from repo paths.")
    parser.add_argument("--include", action="append", default=[], help="File or directory path to include. May be relative to repo root or absolute inside the repo.")
    parser.add_argument("--output-dir", type=Path, default=Path("exports/preflight_context_bundle"), help="Output directory inside the repository.")
    parser.add_argument("--zip-name", default="preflight_context_bundle.zip")
    parser.add_argument("--manifest-name", default="preflight_context_bundle_manifest.json")
    parser.add_argument("--purpose", default="patch_context_only_not_pipeline_input")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.include:
        raise SystemExit("At least one --include path is required.")
    result = create_context_bundle(
        repo_root=ROOT,
        output_dir=args.output_dir,
        include_paths=[Path(item) for item in args.include],
        zip_name=args.zip_name,
        manifest_name=args.manifest_name,
        purpose=args.purpose,
    )
    print("# Preflight Context Bundle")
    print("boundary=context_bundle_only_not_pipeline_input")
    print(f"included_count={len(result.included)}")
    print(f"missing_count={len(result.missing)}")
    print(f"skipped_outside_repo_count={len(result.skipped_outside_repo)}")
    print(f"zip={result.zip_path}")
    print(f"manifest={result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
