"""Pure fail-closed tests; no WSL host or GitHub credentials are required."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "workchat_workspace_gate", Path(__file__).resolve().parents[1] /
    "tools" / "workchat_workspace_gate.py"
)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class WorkspaceGateTests(unittest.TestCase):
    def test_windows_execution_is_denied_before_reading_project_files(self):
        with patch.object(GATE.sys, "platform", "win32"):
            with self.assertRaisesRegex(GATE.GateBlocked, "WSL_ONLY"):
                GATE.verify("before-edit")

    def test_worktree_ancestor_is_exact_not_prefix(self):
        root = Path("/home/jens_h/worktrees/job-application-pipeline")
        self.assertTrue(GATE.within_worktree(root / "feature-a", root))
        self.assertFalse(GATE.within_worktree(root, root))
        self.assertFalse(GATE.within_worktree(Path(str(root) + "-shadow/feature-a"), root))
        self.assertFalse(GATE.within_worktree(Path("/mnt/c/Users/jensh/Documents/Codex/w"), root))

    def test_git_remote_identity_cannot_be_confused(self):
        name = "jenshaberle-dotcom/job-application-pipeline"
        self.assertTrue(GATE.accepted_origin("git@github.com:" + name + ".git", name))
        self.assertTrue(GATE.accepted_origin("https://github.com/" + name, name))
        for wrong in ("https://github.com/" + name + "-evil",
                      "https://github.com/" + name + "/other",
                      "https://evil.test/" + name, "file:///tmp/repo"):
            self.assertFalse(GATE.accepted_origin(wrong, name))

    def test_remote_commit_requires_one_exact_ref(self):
        sha = "a" * 40
        with patch.object(GATE, "git", return_value=sha + "\trefs/heads/main"):
            self.assertEqual(GATE.remote_commit(Path("/missing"), "main"), sha)
        for response in ("", "not-a-sha\trefs/heads/main",
                         sha + "\trefs/heads/other", sha + "\trefs/heads/main\n" +
                         "b" * 40 + "\trefs/heads/main"):
            with patch.object(GATE, "git", return_value=response):
                with self.assertRaises(GATE.GateBlocked):
                    GATE.remote_commit(Path("/missing"), "main")

    def test_restart_blocks_mutation_but_not_readonly_inspection(self):
        blocked = dict(state="BLOCKED_PENDING_HOST_PREFLIGHT",
                       work_admission=dict(normal_new_project_mutation_blocked=True))
        passing = dict(state="PASS",
                       work_admission=dict(normal_new_project_mutation_blocked=False))
        self.assertTrue(GATE.restart_admits(blocked, "inspect"))
        self.assertFalse(GATE.restart_admits(blocked, "before-edit"))
        self.assertFalse(GATE.restart_admits(blocked, "after-push"))
        self.assertTrue(GATE.restart_admits(passing, "before-edit"))
        self.assertFalse(GATE.restart_admits(dict(state="PASS"), "before-edit"))


if __name__ == "__main__":
    unittest.main()
