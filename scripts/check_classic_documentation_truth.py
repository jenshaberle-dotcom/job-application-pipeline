"""Check maintained Classic documentation against implementation and hardcut absence."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def check_truth(root: Path) -> list[str]:
    issues: list[str] = []
    manifest = json.loads((root / 'docs/reference/documentation/hardcut-20261002.json').read_text())
    for path in manifest['deleted_paths']:
        if (root / path).exists():
            issues.append(f'retired documentation restored: {path}')
    for old, new in manifest['moved_contracts'].items():
        if (root / old).exists() or not (root / new).is_file():
            issues.append(f'contract disposition drift: {old} -> {new}')

    demand = json.loads((root / '.rcc/workload-demands.json').read_text())
    execution = (root / 'docs/current/ci-max-execution.md').read_text()
    rows = dict(re.findall(r'^\| `\.github/workflows/([^`]+)` \| `([^`]+)` \|', execution, re.M))
    if rows != demand['workflow_demands']:
        issues.append('documented workflow demand differs from RCC consumer declaration')
    if set(rows) != {p.name for p in (root / '.github/workflows').glob('*.yml')}:
        issues.append('documented workflows differ from repository workflows')

    package = json.loads((root / 'frontend/control-center/package.json').read_text())
    architecture = (root / 'docs/current/architecture.md').read_text()
    if 'react' in package['dependencies'] and 'React' not in architecture:
        issues.append('React implementation missing from current architecture')
    desktop_version = (root / 'windows/JAP.ControlCenter.Desktop/VERSION').read_text().strip()
    readme = (root / 'README.md').read_text()
    if f'Desktop product version: **{desktop_version}**' not in readme:
        issues.append('README desktop version differs from desktop VERSION')
    maintained = [root / 'README.md', root / '.github/RELEASE_MANAGEMENT.md']
    maintained += list((root / 'docs/current').glob('*.md'))
    maintained += list((root / 'docs/guides').glob('*.md'))
    forbidden = (
        r'Jinja2 is the current',
        r'uses Jinja2 as a server-rendered',
        r'runs on GitHub-hosted `windows-latest`',
        r'No active publisher exists',
        r'JAP has exactly two RCC workload targets',
        r'1\.2\.2 is the current',
        r'temporary full-repository ZIP review, and later MCP-backed state',
    )
    for p in maintained:
        text = p.read_text()
        for pattern in forbidden:
            if re.search(pattern, text, re.I):
                issues.append(f'obsolete current claim: {p.relative_to(root)}: {pattern}')
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    issues = check_truth(args.root.resolve())
    print(json.dumps({'status': 'fail' if issues else 'pass', 'issues': issues}, indent=2))
    return 1 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
