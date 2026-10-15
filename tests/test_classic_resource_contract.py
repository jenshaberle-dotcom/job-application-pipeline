"""Consumer resource savings without copying RCC allocation or provider authority."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def test_shallow_candidate_fetches_only_missing_exact_policy_and_keeps_source(tmp_path):
    origin = tmp_path / 'origin'
    origin.mkdir()
    git(origin, 'init', '-q')
    git(origin, 'config', 'user.email', 'test@example.test')
    git(origin, 'config', 'user.name', 'Test')
    (origin / 'scripts').mkdir()
    launcher = origin / 'scripts/run_validation_test_plan.py'
    launcher.write_text('print("trusted policy")\n')
    git(origin, 'add', '.')
    git(origin, 'commit', '-qm', 'policy')
    policy = git(origin, 'rev-parse', 'HEAD')
    launcher.write_text('print("candidate is not launcher authority")\n')
    git(origin, 'commit', '-qam', 'candidate')
    source = git(origin, 'rev-parse', 'HEAD')
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    git(candidate, 'init', '-q')
    git(candidate, 'remote', 'add', 'origin', origin.as_uri())
    git(candidate, 'fetch', '--no-tags', '--depth=1', 'origin', source)
    git(candidate, 'checkout', '-q', '--detach', 'FETCH_HEAD')
    assert subprocess.run(['git', '-C', str(candidate), 'cat-file', '-e', policy], capture_output=True).returncode != 0
    workflow = (ROOT / '.github/workflows/pr-validation.yml').read_text()
    start = workflow.index('          if ! git cat-file')
    end = workflow.index('          "$PR_PYTHON" "$trusted_launcher"', start)
    commands = '\n'.join(line[10:] for line in workflow[start:end].splitlines())
    output = tmp_path / 'trusted.py'
    subprocess.run(['bash', '-euc', commands], cwd=candidate, env=dict(
        os.environ, policy_sha=policy, trusted_launcher=str(output),
    ), check=True, capture_output=True)
    assert output.read_text() == 'print("trusted policy")\n'
    assert git(candidate, 'rev-parse', 'HEAD') == source
    # The dynamic lint path must work without a merge-base or another main fetch.
    start = workflow.index('          if [ -n "$RCC_TEST_PLAN" ]; then')
    end = workflow.index('          existing=()', start)
    commands = '\n'.join(line[10:] for line in workflow[start:end].splitlines())
    run = subprocess.run(['bash', '-euc', commands + '\nprintf "%s" "$changed_output"'], cwd=candidate,
                         env=dict(os.environ, RCC_TEST_PLAN=json.dumps({'policy_sha': policy}),
                                  PR_PYTHON=sys.executable), capture_output=True, text=True, check=True)
    assert run.stdout == 'scripts/run_validation_test_plan.py'


def test_existing_release_reuses_one_response_for_identity_and_assets():
    workflow = (ROOT / '.github/workflows/jap-windows-desktop-host-release.yml').read_text()
    existing = workflow.split('          if ($Exists) {', 1)[1].split('          gh release create', 1)[0]
    assert existing.count('gh api $Api') == 1
    assert '$ExistingRelease.target_commitish' in existing
    assert '$ExistingRelease.assets' in existing
    assert existing.index('$LASTEXITCODE -ne 0') < existing.index('ConvertFrom-Json')
    assert 'reconcile before retry' in workflow


def test_classic_keeps_event_admission_and_no_consumer_pool_control():
    demand = json.loads((ROOT / '.rcc/workload-demands.json').read_text())
    admission = demand['workflow_admission']['pr-validation.yml']
    assert admission['event'] == 'pull_request'
    assert admission['source_binding'] == 'pull_request_head_sha'
    assert admission['auto_dispatch'] is True
    assert demand['authority']['consumer_runner_lifecycle'] is False
    assert demand['authority']['allocation'] == 'RCC_AUTO_ONLY'
    for workflow in (ROOT / '.github/workflows').glob('*.yml'):
        assert 'schedule:' not in workflow.read_text()
