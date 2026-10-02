from pathlib import Path
import shutil

from scripts.check_classic_documentation_truth import check_truth

ROOT = Path(__file__).resolve().parents[1]


def test_current_documentation_matches_implementation_and_absence_contract():
    assert check_truth(ROOT) == []


def _copy_contract_surface(tmp_path):
    for name in ['docs', '.rcc', '.github', 'frontend']:
        shutil.copytree(ROOT / name, tmp_path / name)
    shutil.copyfile(ROOT / 'README.md', tmp_path / 'README.md')
    return tmp_path


def test_retired_plan_cannot_regain_active_authority(tmp_path):
    root = _copy_contract_surface(tmp_path)
    path = root / 'docs/planning/active/demo_001_live_e2e_reentry.md'
    path.write_text('# Restored demo priority\n')
    assert any('retired documentation restored' in issue for issue in check_truth(root))


def test_new_workload_requires_documentation_update(tmp_path):
    root = _copy_contract_surface(tmp_path)
    (root / '.github/workflows/undocumented.yml').write_text('name: undocumented\n')
    assert 'documented workflows differ from repository workflows' in check_truth(root)


def test_old_hosted_publisher_claim_is_rejected(tmp_path):
    root = _copy_contract_surface(tmp_path)
    (root / '.github/RELEASE_MANAGEMENT.md').write_text('No active publisher exists.\n')
    assert any('obsolete current claim' in issue for issue in check_truth(root))
