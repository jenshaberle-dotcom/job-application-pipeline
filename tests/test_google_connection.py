import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import product_v1_google_connection as google


class GoogleConnectionTests(unittest.TestCase):
    def tearDown(self):
        google._attempt.clear()

    def test_rejects_cross_origin_missing_header_and_other_port(self):
        for origin in ("https://evil.example", "http://127.0.0.1:9000", "null"):
            self.assertFalse(google.trusted_ui_request(
                {"Origin": origin, "X-JAP-Action": "google-connect"}, ("127.0.0.1", 8780)))
        self.assertFalse(google.trusted_ui_request(
            {"Origin": "http://127.0.0.1:8780"}, ("127.0.0.1", 8780)))
        self.assertTrue(google.trusted_ui_request(
            {"Origin": "http://127.0.0.1:8780", "X-JAP-Action": "google-connect"},
            ("127.0.0.1", 8780)))

    def test_invalid_grant_is_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "status.json").write_text('{"message":"invalid_grant SECRET"}')
            with patch.object(google, "_state_root", return_value=root):
                self.assertEqual(google.connection_status(), {"state": "reauth_required"})

    def test_duplicate_click_does_not_start_another_process(self):
        google._attempt.update(state="awaiting_google")
        with patch.object(google.threading, "Thread") as thread:
            self.assertEqual(google.start_connection(), {"state": "awaiting_google"})
            thread.assert_not_called()

    def test_missing_setup_does_not_start_login(self):
        with patch.object(google, "_client_config", return_value=Path("/absent/test.json")):
            self.assertEqual(google.start_connection(), {"state": "setup_required"})

    def test_failure_does_not_expose_bridge_output(self):
        with patch.object(google.subprocess, "Popen", side_effect=OSError("SECRET")):
            google._authorize()
        self.assertEqual(google.connection_status(), {"state": "login_failed"})
