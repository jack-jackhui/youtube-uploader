#!/usr/bin/env python3
"""
Test auto_publish_checker without actual YouTube API calls.
"""
import sys
sys.path.insert(0, "/home/jack/youtube-uploader")

from unittest.mock import Mock, patch
from auto_publish_checker import AutoPublishChecker, VideoStatus, AutoPublishResult

def test_video_status_parsing():
    """Test that VideoStatus correctly parses API response."""
    print("Test 1: VideoStatus parsing")
    
    # Mock a successful video response
    mock_response = {
        "items": [{
            "status": {
                "uploadStatus": "processed",
                "privacyStatus": "private",
                "embeddable": True,
                "license": "youtube",
                "publicStatsViewable": True,
            },
            "processingDetails": {
                "processingStatus": "succeeded",
            },
            "contentDetails": {}
        }]
    }
    
    # Create mock YouTube service
    mock_youtube = Mock()
    mock_youtube.videos().list().execute.return_value = mock_response
    
    checker = AutoPublishChecker(youtube_service=mock_youtube)
    status = checker.get_video_status("test123")
    
    assert status.upload_status == "processed", f"Expected 'processed', got '{status.upload_status}'"
    assert status.processing_status == "succeeded", f"Expected 'succeeded', got '{status.processing_status}'"
    assert status.is_processed == True, "Expected is_processed=True"
    assert status.is_clean == True, "Expected is_clean=True (no issues)"
    assert len(status.issues) == 0, f"Expected no issues, got {status.issues}"
    print("  PASS: Clean video correctly identified")
    
def test_rejection_detection():
    """Test that rejections are detected."""
    print("Test 2: Rejection detection")
    
    mock_response = {
        "items": [{
            "status": {
                "uploadStatus": "rejected",
                "privacyStatus": "private",
                "rejectionReason": "duplicate",
            },
            "processingDetails": {},
            "contentDetails": {}
        }]
    }
    
    mock_youtube = Mock()
    mock_youtube.videos().list().execute.return_value = mock_response
    
    checker = AutoPublishChecker(youtube_service=mock_youtube)
    status = checker.get_video_status("test456")
    
    assert status.is_clean == False, "Expected is_clean=False for rejected video"
    assert len(status.issues) > 0, "Expected issues for rejected video"
    assert any("duplicate" in issue.lower() for issue in status.issues), f"Expected duplicate issue, got {status.issues}"
    print("  PASS: Rejection correctly detected")

def test_processing_failure():
    """Test that processing failures are detected."""
    print("Test 3: Processing failure detection")
    
    mock_response = {
        "items": [{
            "status": {
                "uploadStatus": "failed",
                "privacyStatus": "private",
                "failureReason": "codec",
            },
            "processingDetails": {
                "processingStatus": "failed",
            },
            "contentDetails": {}
        }]
    }
    
    mock_youtube = Mock()
    mock_youtube.videos().list().execute.return_value = mock_response
    
    checker = AutoPublishChecker(youtube_service=mock_youtube)
    status = checker.get_video_status("test789")
    
    assert status.is_clean == False, "Expected is_clean=False for failed video"
    assert status.is_processed == False, "Expected is_processed=False for failed video"
    print("  PASS: Processing failure correctly detected")

def test_config_from_env():
    """Test that config is loaded from environment."""
    print("Test 4: Config from environment")
    
    import os
    os.environ["YOUTUBE_AUTO_PUBLISH_AFTER_CHECK"] = "true"
    os.environ["YOUTUBE_CHECK_WAIT_MINUTES"] = "15"
    os.environ["YOUTUBE_CHECK_INTERVAL_SECONDS"] = "10"
    os.environ["YOUTUBE_AUTO_PUBLISH_PRIVACY"] = "unlisted"
    
    checker = AutoPublishChecker()
    
    assert checker.enabled == True, f"Expected enabled=True, got {checker.enabled}"
    assert checker.max_wait_minutes == 15, f"Expected max_wait=15, got {checker.max_wait_minutes}"
    assert checker.check_interval_seconds == 10, f"Expected interval=10, got {checker.check_interval_seconds}"
    assert checker.target_privacy == "unlisted", f"Expected privacy=unlisted, got {checker.target_privacy}"
    print("  PASS: Config loaded from environment")
    
    # Clean up
    del os.environ["YOUTUBE_AUTO_PUBLISH_AFTER_CHECK"]
    del os.environ["YOUTUBE_CHECK_WAIT_MINUTES"]
    del os.environ["YOUTUBE_CHECK_INTERVAL_SECONDS"]
    del os.environ["YOUTUBE_AUTO_PUBLISH_PRIVACY"]

def test_dry_run():
    """Test dry run mode doesn't publish."""
    print("Test 5: Dry run mode")
    
    mock_response = {
        "items": [{
            "status": {
                "uploadStatus": "processed",
                "privacyStatus": "private",
            },
            "processingDetails": {
                "processingStatus": "succeeded",
            },
            "contentDetails": {}
        }]
    }
    
    mock_youtube = Mock()
    mock_youtube.videos().list().execute.return_value = mock_response
    
    # Enable auto-publish
    import os
    os.environ["YOUTUBE_AUTO_PUBLISH_AFTER_CHECK"] = "true"
    
    checker = AutoPublishChecker(youtube_service=mock_youtube)
    
    # Mock email at the module level where it's imported
    with patch('email_notifier.send_email'):
        result = checker.check_and_publish("testdry", dry_run=True)
    
    assert result.published == False, "Dry run should not publish"
    assert "dry run" in result.reason.lower(), f"Expected dry run reason, got {result.reason}"
    print("  PASS: Dry run doesn't publish")
    
    del os.environ["YOUTUBE_AUTO_PUBLISH_AFTER_CHECK"]

def test_content_id_warning():
    """Test that Content ID limitation is clearly warned."""
    print("Test 6: Content ID warning")
    
    mock_response = {
        "items": [{
            "status": {
                "uploadStatus": "processed",
                "privacyStatus": "private",
            },
            "processingDetails": {
                "processingStatus": "succeeded",
            },
            "contentDetails": {}
        }]
    }
    
    mock_youtube = Mock()
    mock_youtube.videos().list().execute.return_value = mock_response
    
    checker = AutoPublishChecker(youtube_service=mock_youtube)
    status = checker.get_video_status("testwarning")
    
    assert len(status.warnings) > 0, "Expected warnings about Content ID"
    assert any("content id" in w.lower() for w in status.warnings), f"Expected Content ID warning, got {status.warnings}"
    print("  PASS: Content ID limitation warned")

def test_disabled_by_default():
    """Test that auto-publish is disabled by default."""
    print("Test 7: Disabled by default")
    
    import os
    # Ensure env var is not set
    if "YOUTUBE_AUTO_PUBLISH_AFTER_CHECK" in os.environ:
        del os.environ["YOUTUBE_AUTO_PUBLISH_AFTER_CHECK"]
    
    checker = AutoPublishChecker()
    assert checker.enabled == False, f"Expected disabled by default, got enabled={checker.enabled}"
    
    # Also test that check_and_publish returns early when disabled
    mock_youtube = Mock()
    checker = AutoPublishChecker(youtube_service=mock_youtube)
    result = checker.check_and_publish("test", dry_run=False)
    
    assert result.published == False, "Should not publish when disabled"
    assert "disabled" in result.reason.lower(), f"Expected disabled reason, got {result.reason}"
    print("  PASS: Auto-publish disabled by default")

if __name__ == "__main__":
    print("=" * 60)
    print("Auto-Publish Checker Tests")
    print("=" * 60)
    
    try:
        test_video_status_parsing()
        test_rejection_detection()
        test_processing_failure()
        test_config_from_env()
        test_dry_run()
        test_content_id_warning()
        test_disabled_by_default()
        
        print("=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
    except AssertionError as e:
        print(f"TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
