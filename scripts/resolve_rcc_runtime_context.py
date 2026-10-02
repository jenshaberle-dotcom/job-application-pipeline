"""Read the RCC Demand-v2 Linux runtime projection; no runner lifecycle effects."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def resolve(context: dict, *, repository_id: int, repository: str,
            runner: str, source_sha: str) -> str:
    expected = {
        "RepositoryId": repository_id,
        "Repository": repository,
        "RunnerName": runner,
        "Platform": "linux-wsl",
        "SourceSha": source_sha,
        "Status": "PASS",
    }
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("invalid exact source SHA")
    for key, value in expected.items():
        if context.get(key) != value:
            raise ValueError(f"RCC runtime context mismatch: {key}")
    if context.get("PrimaryFailure") not in (None, ""):
        raise ValueError("RCC runtime context has a failure")
    if not isinstance(context.get("ProfileId"), str) or not context["ProfileId"].strip():
        raise ValueError("RCC runtime profile identity missing")
    if not re.fullmatch(r"[0-9a-f]{64}", str(context.get("ProfileHash", ""))):
        raise ValueError("RCC runtime profile hash invalid")
    interpreter = context.get("Interpreter")
    if (not isinstance(interpreter, str) or not interpreter
            or any(character in interpreter for character in "\r\n")
            or not Path(interpreter).is_absolute()):
        raise ValueError("RCC runtime interpreter must be an absolute single-line path")
    return interpreter


def main() -> int:
    try:
        path, repository_id, repository, runner, source_sha = sys.argv[1:]
        context = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(context, dict):
            raise ValueError("RCC runtime projection must be an object")
        print(resolve(context, repository_id=int(repository_id), repository=repository,
                      runner=runner, source_sha=source_sha))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
