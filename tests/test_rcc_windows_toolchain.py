"""Execute the PowerShell resolver; a host-PATH tool cannot qualify a packet."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PWSH = shutil.which('pwsh')
pytestmark = pytest.mark.skipif(os.name != 'posix' or PWSH is None,
                              reason='PowerShell semantic fixture uses POSIX executable stubs')


def fixture(tmp_path: Path):
    tools = tmp_path / 'packets'
    tools.mkdir()
    for name, version in [('node', 'v22.23.3'), ('dotnet', '8.0.425')]:
        path = tools / (name + '.exe')
        path.write_text('#!/bin/sh\nprintf "%s\\n" "' + version + '"\n')
        path.chmod(0o755)
    python = tmp_path / 'qualified-python.exe'
    python.write_text('qualified interpreter')
    context = {'RepositoryId': 1230805345, 'Repository': 'jenshaberle-dotcom/job-application-pipeline',
               'RunnerName': 'assigned-facade', 'SourceSha': 'a' * 40, 'Platform': 'windows',
               'Status': 'PASS', 'ProfileId': 'assigned-profile', 'ProfileHash': 'b' * 64,
               'Interpreter': str(python), 'ToolPaths': [str(tools)],
               'ToolVersions': {'node-22': '22.23.3', 'dotnet-sdk-8': '8.0.425'}}
    return context


def invoke(tmp_path, context):
    path = tmp_path / 'context.json'
    path.write_text(json.dumps(context))
    gh_path = tmp_path / 'github-path'
    gh_env = tmp_path / 'github-env'
    result = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-File',
                             str(ROOT / 'scripts/resolve_rcc_windows_toolchain.ps1'),
                             '-ContextFile', str(path), '-Repository', context['Repository'],
                             '-Runner', 'assigned-facade', '-SourceSha', 'a' * 40],
                            env={**os.environ, 'GITHUB_PATH': str(gh_path), 'GITHUB_ENV': str(gh_env)},
                            capture_output=True, text=True, timeout=30)
    return result, gh_path, gh_env


def test_only_qualified_packet_paths_are_activated(tmp_path):
    context = fixture(tmp_path)
    result, gh_path, gh_env = invoke(tmp_path, context)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == context['Interpreter']
    assert gh_path.read_text().strip() == context['ToolPaths'][0]
    assert 'DOTNET_ROOT=' + context['ToolPaths'][0] in gh_env.read_text()


@pytest.mark.parametrize('key,value', [('SourceSha', 'c' * 40), ('Status', 'FAIL'),
                                     ('ToolPaths', []), ('ToolVersions', {}),
                                     ('ToolPaths', ['/tmp\nINJECTED=1']), ('ProfileHash', '')])
def test_stale_or_unqualified_tools_cannot_publish_paths(tmp_path, key, value):
    context = fixture(tmp_path)
    context[key] = value
    result, gh_path, gh_env = invoke(tmp_path, context)
    assert result.returncode != 0
    assert not gh_path.exists()
    assert not gh_env.exists()


def test_host_path_never_rescues_a_missing_packet_or_version_drift(tmp_path):
    context = fixture(tmp_path)
    node = Path(context['ToolPaths'][0]) / 'node.exe'
    node.write_text('#!/bin/sh\necho v22.23.2\n')
    result, gh_path, _ = invoke(tmp_path, context)
    assert result.returncode != 0
    assert not gh_path.exists()
    node.unlink()
    result, gh_path, _ = invoke(tmp_path, context)
    assert result.returncode != 0
    assert not gh_path.exists()
