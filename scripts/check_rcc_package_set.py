"""Require the RCC package lock to cover JAP's declared product and test dependencies."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def check(root: Path = ROOT) -> list[str]:
    demand = json.loads((root / '.rcc/workload-demands.json').read_text())
    package = demand['project_runtime']['python']['package_set']
    path = root / package['path']
    errors = []
    if hashlib.sha256(path.read_bytes()).hexdigest() != package['sha256']:
        errors.append('RCC package-set content hash drift')
    locked = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^ ]+) ((?:--hash=sha256:[0-9a-f]{64})(?: --hash=sha256:[0-9a-f]{64})*)', line)
        if not match:
            errors.append(f'Invalid pinned/hash-qualified lock entry: {line}')
            continue
        name, version, _ = match.groups()
        key = canonicalize_name(name)
        if key in locked:
            errors.append(f'Duplicate lock package: {name}')
        locked[key] = version
    for filename in ('requirements.txt', 'requirements-dev.txt'):
        for line in (root / filename).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith(('#', '-r ')):
                continue
            required = Requirement(line)
            version = locked.get(canonicalize_name(required.name))
            if version is None or version not in required.specifier:
                errors.append(f'{filename}: RCC lock does not satisfy {line}')
    return errors


def main() -> int:
    errors = check()
    for error in errors:
        print(error)
    print('JAP_RCC_PACKAGE_SET=' + ('FAIL' if errors else 'PASS'))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
