from pathlib import Path
import shutil

from scripts.check_rcc_package_set import ROOT, check


def test_rcc_lock_covers_declared_product_and_test_dependencies() -> None:
    assert check() == []


def test_new_product_dependency_cannot_escape_rcc_demand(tmp_path: Path) -> None:
    shutil.copytree(ROOT / '.rcc', tmp_path / '.rcc')
    for filename in ('requirements.txt', 'requirements-dev.txt'):
        shutil.copyfile(ROOT / filename, tmp_path / filename)
    with (tmp_path / 'requirements.txt').open('a') as file:
        file.write('\nmissing-product-dependency==1.0\n')
    assert any('missing-product-dependency' in error for error in check(tmp_path))


def test_incompatible_pin_is_rejected_even_when_lock_contains_package(tmp_path: Path) -> None:
    shutil.copytree(ROOT / '.rcc', tmp_path / '.rcc')
    for filename in ('requirements.txt', 'requirements-dev.txt'):
        shutil.copyfile(ROOT / filename, tmp_path / filename)
    path = tmp_path / 'requirements.txt'
    path.write_text(path.read_text().replace('extruct==0.18.0', 'extruct==99.0.0'))
    assert any('extruct==99.0.0' in error for error in check(tmp_path))


def test_reviewed_seed_matches_locked_hash_and_upstream_module() -> None:
    import hashlib
    import json
    import zipfile
    seed = ROOT / '.rcc/python-package-sets/wheel-seeds'
    provenance = json.loads((seed / 'jstyleson-0.0.2.provenance.json').read_text())
    wheel = seed / provenance['wheel_filename']
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    demand = json.loads((ROOT / '.rcc/workload-demands.json').read_text())
    assert demand['project_runtime']['python']['package_set']['wheel_seeds'] == [{
        'path': str(wheel.relative_to(ROOT)),
        'sha256': digest,
        'provenance_path': str((seed / 'jstyleson-0.0.2.provenance.json').relative_to(ROOT)),
    }]
    assert digest == provenance['wheel_sha256']
    assert '--hash=sha256:' + digest in (ROOT / '.rcc/python-package-sets/jap-product-v1.txt').read_text()
    assert provenance['source_changes'] is False
    with zipfile.ZipFile(wheel) as archive:
        assert 'jstyleson.py' in archive.namelist()
        assert not any(name.endswith(('.so', '.dll', '.exe')) for name in archive.namelist())
