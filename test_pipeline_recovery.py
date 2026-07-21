import os
import tempfile
import unittest
from unittest.mock import Mock, mock_open, patch

import main
import video_api_call
import cta_overlay
import youtube_manager


class RecoveredPipelineTests(unittest.TestCase):
    def test_outline_notes_are_naturalized_with_campaign_url(self):
        entry = {
            "hook": "Start here",
            "script_outline": "Explain why resumes fail; Close with a clear spoken call-to-action to link in bio",
            "cta": "CTA to winning-cv.jackhui.com.au",
        }
        script = main._compose_backlog_script(entry, {"product_url": "https://winning-cv.jackhui.com.au/"})
        lower = script.lower()
        for producer_note in ("explain", "close with", "call-to-action", "link in bio", "cta to"):
            self.assertNotIn(producer_note, lower)
        self.assertIn("winning-cv.jackhui.com.au", lower)

    @patch("video_api_call.requests.post")
    @patch("video_api_call._select_approved_bgm", return_value="")
    def test_video_api_disables_default_ending(self, _bgm, post):
        response = Mock()
        response.json.return_value = {"data": {"task_id": "task-1"}}
        post.return_value = response
        result = video_api_call.generate_video(
            "key", "https://video.invalid", "subject", "script", ["term"], "voice",
            include_default_ending=False,
        )
        self.assertFalse(post.call_args.kwargs["json"]["include_default_ending"])
        self.assertTrue(result["original"].endswith("/task-1/final-1.mp4"))

    def test_custom_ending_is_appended_after_overlay(self):
        metadata = {
            "cta_overlay": {"enabled": True},
            "ending_video": {"enabled": True, "path": "ending.mp4"},
        }
        with patch("cta_overlay.apply_cta_overlay", return_value="overlaid.mp4") as overlay, \
             patch("cta_overlay.append_ending_video", return_value="final.mp4") as ending:
            result = cta_overlay.process_video_with_overlay("raw.mp4", metadata)
        overlay.assert_called_once()
        ending.assert_called_once_with("overlaid.mp4", "ending.mp4")
        self.assertEqual(result["processed_path"], "final.mp4")
        self.assertTrue(result["ending_appended"])

    def test_youtube_auth_uses_separate_scope_credentials(self):
        class Creds:
            valid = True
            expired = False
            refresh_token = "present"
            def has_scopes(self, scopes):
                self.scopes = scopes
                return True
        creds = Creds()
        opened = []
        def fake_open(path, mode):
            opened.append(path)
            return mock_open(read_data=b"x")()
        with patch("youtube_manager.os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=fake_open), \
             patch("youtube_manager.pickle.load", return_value=creds), \
             patch("youtube_manager.build", return_value="service"):
            self.assertEqual(youtube_manager.authenticate_youtube(), "service")
            self.assertTrue(opened[-1].endswith("youtube_credentials.pickle"))
            self.assertEqual(youtube_manager.authenticate_youtube(require_force_ssl=True), "service")
            self.assertTrue(opened[-1].endswith("youtube_force_ssl_credentials.pickle"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
