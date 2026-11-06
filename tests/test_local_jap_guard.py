"""Isolated local bare-repo tests; no real GitHub access or production checkout."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts import local_jap_guard as tool


def git(path, *args):
    p = subprocess.run(['git','-C',str(path),*args],check=True,capture_output=True,text=True)
    return p.stdout.strip()


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.remote = self.base/'remote.git'
        self.repo = self.base/'repo'
        self.out = self.base/'receipts'
        self.out.mkdir()
        subprocess.run(['git','init','--bare','--quiet',str(self.remote)],check=True)
        subprocess.run(['git','init','--quiet','--initial-branch=main',str(self.repo)],check=True)
        git(self.repo,'config','user.email','test@localhost')
        git(self.repo,'config','user.name','Local Test')
        (self.repo/'src').mkdir()
        (self.repo/'src'/'thing.py').write_text('x=1\n')
        (self.repo/'README.md').write_text('# Test\n')
        git(self.repo,'add','-A')
        git(self.repo,'commit','-qm','baseline')
        git(self.repo,'remote','add','origin',str(self.remote))
        git(self.repo,'push','-q','-u','origin','main')

    def tearDown(self):
        self.tmp.cleanup()

    def test_safe_paths(self):
        self.assertTrue(tool.is_safe(Path('src/thing.py')))
        self.assertTrue(tool.is_safe(Path('tests/test_file.py')))
        self.assertFalse(tool.is_safe(Path('data/db.json')))
        self.assertFalse(tool.is_safe(Path('src/.env')))
        self.assertFalse(tool.is_safe(Path('scripts/token.json')))
        self.assertFalse(tool.is_safe(Path('tests/__pycache__/test.py')))

    def test_plan_is_local_read_only_and_lists_candidate_hashes(self):
        before = git(self.repo, 'status', '--porcelain=v1')
        result = tool.plan_snapshot(self.repo, 'test/repo', self.out)
        data = json.loads(Path(result['plan']).read_text())
        self.assertIn('src/thing.py', data['selected_paths_sha256'])
        self.assertIn('README.md', data['selected_paths_sha256'])
        self.assertEqual(before, git(self.repo, 'status', '--porcelain=v1'))
        self.assertFalse((self.out / 'repo-backup.json').exists())

    def test_snapshot_includes_uncommitted_code_without_touching_checkout(self):
        (self.repo/'src'/'thing.py').write_text('x=2\n')
        (self.repo/'scripts').mkdir()
        (self.repo/'scripts'/'new.py').write_text('new=1\n')
        (self.repo/'data').mkdir()
        (self.repo/'data'/'private.json').write_text('{"email":"not-for-github"}')
        (self.repo/'.env').write_text('PRIVATE=foo')
        before = git(self.repo,'status','--porcelain=v1')
        result = tool.backup(self.repo,'test/repo',self.out)
        after = git(self.repo,'status','--porcelain=v1')
        self.assertEqual(before,after)
        self.assertTrue(result['remote_verified'])
        branch = result['backup_branch']
        names=git(self.remote,'ls-tree','-r','--name-only',branch).splitlines()
        self.assertIn('src/thing.py',names)
        self.assertIn('scripts/new.py',names)
        self.assertIn('JAP_LOCAL_SOURCE_SNAPSHOT.json',names)
        self.assertNotIn('.env',names)
        self.assertNotIn('data/private.json',names)
        self.assertEqual(git(self.remote,'show',branch+':src/thing.py'),'x=2')
        self.assertEqual(len(git(self.remote,'rev-list','--all','--max-count=1').splitlines()),1)

    def test_secret_blocks_before_push(self):
        (self.repo/'src'/'secret.py').write_text('secret="ghp_'+ 'A'*35+'"\n')
        with self.assertRaisesRegex(tool.GateError,'NO PUSH'):
            tool.backup(self.repo,'test/repo',self.out)
        self.assertFalse((self.out/'repo-backup.json').exists())

    def test_stage_then_apply_isolated_and_ff_only(self):
        # Create an isolated PoC branch that is based on the original main.
        git(self.repo,'switch','-q','-c',tool.POC)
        (self.repo/'tests').mkdir()
        (self.repo/'tests'/'test_dummy.py').write_text('def test_hello(): assert True\n')
        git(self.repo,'add','tests/test_dummy.py')
        git(self.repo,'commit','-qm','new POC code')
        git(self.repo,'push','-q','origin',tool.POC)
        git(self.repo,'switch','-q','main')
        for name in ('job-application-pipeline','job-pipeline-runtime'):
            (self.out/f'{name}-backup.json').write_text('{"remote_verified":true}')
        prev=tool.TESTS
        tool.TESTS=('tests/test_dummy.py',)
        try:
            staged=tool.stage_poc(self.repo,self.out)
        finally:
            tool.TESTS=prev
        self.assertEqual(staged['status'],'staged_tested_not_applied')
        self.assertFalse((self.repo/'tests'/'test_dummy.py').exists())
        applied=tool.apply_poc(self.repo,self.out)
        self.assertEqual(applied['status'],'applied_locally_not_pushed')
        self.assertTrue((self.repo/'tests'/'test_dummy.py').exists())

    def test_apply_rejects_dirty_worktree(self):
        (self.out/'integration-receipt.json').write_text(json.dumps({
            'status':'staged_tested_not_applied', 'tests_passed':True,
            'source_path':str(self.repo), 'base_branch':'main',
            'base_sha':git(self.repo,'rev-parse','HEAD'),
            'integration_branch':'unknown', 'integration_sha':'x'*40,
        }))
        (self.repo/'src'/'thing.py').write_text('dirty=1\n')
        with self.assertRaisesRegex(tool.GateError,'clean'):
            tool.apply_poc(self.repo,self.out)

if __name__ == '__main__':
    unittest.main()

