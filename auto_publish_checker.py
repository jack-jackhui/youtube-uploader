#!/usr/bin/env python3
"""
Auto-publish checker for YouTube videos.

After uploading a video as private, this module polls YouTube API to check:
1. Processing status (uploaded, processing, processed, failed)
2. Upload status (deleted, failed, processed, rejected, uploaded)
3. Rejection/failure reasons (if any)

Note: YouTube Data API does NOT expose Content ID claims directly.
This module can only detect:
- Processing failures
- Rejection reasons (e.g., duplicate, inappropriate)
- Upload failures

Content ID claims are NOT detectable via API. To mitigate:
- Videos are only auto-published if YOUTUBE_AUTO_PUBLISH_AFTER_CHECK=true
- Conservative default: disabled
- Clear logging when claim status cannot be verified

Usage:
    from auto_publish_checker import AutoPublishChecker
    
    checker = AutoPublishChecker()
    result = checker.check_and_publish(video_id)
    
    if result["published"]:
        print(f"Video published: {result['video_id']}")
    else:
        print(f"Video kept private: {result['reason']}")
"""

import os
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Processing status values from YouTube API
PROCESSING_STATUS = {
    "processing": "Video is being processed",
    "succeeded": "Video has been processed successfully", 
    "failed": "Processing failed",
    "terminated": "Processing was terminated",
}

# Upload status values from YouTube API
UPLOAD_STATUS = {
    "deleted": "Video was deleted",
    "failed": "Upload failed",
    "processed": "Upload completed and processed",
    "rejected": "Upload was rejected",
    "uploaded": "Upload complete, processing pending",
}

# Known rejection reasons
REJECTION_REASONS = {
    "claim": "Video has a copyright claim",
    "copyright": "Video was rejected for copyright",
    "duplicate": "Video is a duplicate",
    "inappropriate": "Video was flagged as inappropriate",
    "length": "Video exceeds length limits",
    "termsOfUse": "Video violates terms of use",
    "trademark": "Video has trademark issues",
    "uploaderAccountClosed": "Uploader account closed",
    "uploaderAccountSuspended": "Uploader account suspended",
}


@dataclass
class VideoStatus:
    """Status of a YouTube video from API check."""
    video_id: str
    upload_status: str = ""
    processing_status: str = ""
    privacy_status: str = ""
    rejection_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    embeddable: bool = True
    license: str = ""
    public_stats_viewable: bool = True
    
    # Computed fields
    is_processed: bool = False
    is_clean: bool = False
    issues: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass 
class AutoPublishResult:
    """Result of auto-publish check."""
    video_id: str
    published: bool = False
    previous_privacy: str = "private"
    new_privacy: str = "private"
    reason: str = ""
    status: Optional[VideoStatus] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        if self.status:
            d["status"] = self.status.to_dict()
        return d


class AutoPublishChecker:
    """
    Checks YouTube video processing status and auto-publishes if clean.
    
    Config via environment:
        YOUTUBE_AUTO_PUBLISH_AFTER_CHECK: Enable auto-publish (default: false)
        YOUTUBE_CHECK_WAIT_MINUTES: Max time to wait for processing (default: 30)
        YOUTUBE_CHECK_INTERVAL_SECONDS: Polling interval (default: 30)
        YOUTUBE_CLEAN_CHECK_REQUIRES_NO_REJECTION: Fail if any rejection (default: true)
        YOUTUBE_AUTO_PUBLISH_PRIVACY: Target privacy after check (default: public)
    """
    
    def __init__(self, youtube_service=None):
        """
        Initialize checker.
        
        Args:
            youtube_service: Authenticated YouTube API service. If None, will authenticate.
        """
        self.youtube = youtube_service
        
        # Load config from environment
        self.enabled = os.getenv("YOUTUBE_AUTO_PUBLISH_AFTER_CHECK", "false").lower() == "true"
        self.max_wait_minutes = int(os.getenv("YOUTUBE_CHECK_WAIT_MINUTES", "30"))
        self.check_interval_seconds = int(os.getenv("YOUTUBE_CHECK_INTERVAL_SECONDS", "30"))
        self.require_no_rejection = os.getenv("YOUTUBE_CLEAN_CHECK_REQUIRES_NO_REJECTION", "true").lower() == "true"
        self.target_privacy = os.getenv("YOUTUBE_AUTO_PUBLISH_PRIVACY", "public")
        
    def _ensure_youtube_service(self):
        """Ensure we have an authenticated YouTube service."""
        if self.youtube is None:
            from youtube_manager import authenticate_youtube
            self.youtube = authenticate_youtube(require_force_ssl=True)
    
    def get_video_status(self, video_id: str) -> VideoStatus:
        """
        Get current status of a video from YouTube API.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            VideoStatus with all available status info
        """
        self._ensure_youtube_service()
        
        # Request all relevant parts
        # Note: processingDetails requires the uploader's auth
        request = self.youtube.videos().list(
            part="status,processingDetails,contentDetails",
            id=video_id
        )
        response = request.execute()
        
        if not response.get("items"):
            raise ValueError(f"Video not found: {video_id}")
        
        item = response["items"][0]
        status_data = item.get("status", {})
        processing_data = item.get("processingDetails", {})
        content_data = item.get("contentDetails", {})
        
        video_status = VideoStatus(
            video_id=video_id,
            upload_status=status_data.get("uploadStatus", ""),
            processing_status=processing_data.get("processingStatus", ""),
            privacy_status=status_data.get("privacyStatus", ""),
            rejection_reason=status_data.get("rejectionReason"),
            failure_reason=status_data.get("failureReason"),
            embeddable=status_data.get("embeddable", True),
            license=status_data.get("license", ""),
            public_stats_viewable=status_data.get("publicStatsViewable", True),
        )
        
        # Determine if processed
        video_status.is_processed = (
            video_status.upload_status == "processed" or
            video_status.processing_status == "succeeded"
        )
        
        # Determine if clean (no issues detected)
        issues = []
        warnings = []
        
        if video_status.rejection_reason:
            reason_desc = REJECTION_REASONS.get(
                video_status.rejection_reason, 
                f"Rejected: {video_status.rejection_reason}"
            )
            issues.append(reason_desc)
        
        if video_status.failure_reason:
            issues.append(f"Processing failed: {video_status.failure_reason}")
        
        if video_status.upload_status == "failed":
            issues.append("Upload failed")
        
        if video_status.upload_status == "rejected":
            issues.append("Upload rejected")
        
        if video_status.upload_status == "deleted":
            issues.append("Video was deleted")
        
        if video_status.processing_status == "failed":
            issues.append("Processing failed")
        
        if video_status.processing_status == "terminated":
            issues.append("Processing was terminated")
        
        # Note: We CANNOT detect Content ID claims via API
        # This is a known limitation
        warnings.append(
            "Content ID claim status cannot be verified via API. "
            "Video may still receive claims after publishing."
        )
        
        video_status.issues = issues
        video_status.warnings = warnings
        video_status.is_clean = len(issues) == 0
        
        return video_status
    
    def wait_for_processing(self, video_id: str) -> Tuple[VideoStatus, bool]:
        """
        Wait for video processing to complete.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Tuple of (VideoStatus, timed_out)
        """
        start_time = time.time()
        max_wait_seconds = self.max_wait_minutes * 60
        
        print(f"[AutoPublish] Waiting for video {video_id} to process...")
        print(f"[AutoPublish] Max wait: {self.max_wait_minutes} minutes, interval: {self.check_interval_seconds}s")
        
        while True:
            elapsed = time.time() - start_time
            
            if elapsed > max_wait_seconds:
                print(f"[AutoPublish] Timeout after {self.max_wait_minutes} minutes")
                status = self.get_video_status(video_id)
                return status, True
            
            status = self.get_video_status(video_id)
            
            print(f"[AutoPublish] Check at {int(elapsed)}s: "
                  f"upload={status.upload_status}, processing={status.processing_status}")
            
            # Check for terminal states
            if status.is_processed:
                print(f"[AutoPublish] Processing complete")
                return status, False
            
            if status.issues:
                print(f"[AutoPublish] Issues detected: {status.issues}")
                return status, False
            
            # Wait before next check
            time.sleep(self.check_interval_seconds)
    
    def publish_video(self, video_id: str, privacy: str = None) -> bool:
        """
        Publish a video by changing its privacy status.
        
        Args:
            video_id: YouTube video ID
            privacy: Target privacy status (default: from config)
            
        Returns:
            True if successful
        """
        self._ensure_youtube_service()
        
        privacy = privacy or self.target_privacy
        
        from youtube_manager import update_video_privacy
        update_video_privacy(self.youtube, video_id, privacy)
        
        return True
    
    def check_and_publish(self, video_id: str, dry_run: bool = False) -> AutoPublishResult:
        """
        Main entry point: wait for processing, check status, and publish if clean.
        
        Args:
            video_id: YouTube video ID
            dry_run: If True, don't actually publish (for testing)
            
        Returns:
            AutoPublishResult with outcome details
        """
        result = AutoPublishResult(
            video_id=video_id,
            previous_privacy="private",
        )
        
        if not self.enabled and not dry_run:
            result.reason = "Auto-publish disabled (YOUTUBE_AUTO_PUBLISH_AFTER_CHECK=false)"
            print(f"[AutoPublish] {result.reason}")
            return result
        
        try:
            # Wait for processing
            status, timed_out = self.wait_for_processing(video_id)
            result.status = status
            result.previous_privacy = status.privacy_status
            
            if timed_out:
                result.reason = f"Processing timeout after {self.max_wait_minutes} minutes"
                self._notify_kept_private(video_id, result.reason, status)
                return result
            
            if not status.is_processed:
                result.reason = f"Processing incomplete: upload={status.upload_status}"
                self._notify_kept_private(video_id, result.reason, status)
                return result
            
            if status.issues:
                result.reason = f"Issues detected: {'; '.join(status.issues)}"
                self._notify_kept_private(video_id, result.reason, status)
                return result
            
            # All checks passed - publish if not dry run
            if dry_run:
                result.reason = "Dry run - would publish"
                result.published = False
                print(f"[AutoPublish] DRY RUN: Would publish {video_id} as {self.target_privacy}")
            else:
                print(f"[AutoPublish] All checks passed. Publishing as {self.target_privacy}...")
                self.publish_video(video_id)
                result.published = True
                result.new_privacy = self.target_privacy
                result.reason = "All checks passed"
                self._notify_published(video_id, status)
            
            return result
            
        except Exception as e:
            result.reason = f"Error: {str(e)}"
            logger.exception(f"Auto-publish check failed for {video_id}")
            self._notify_error(video_id, e)
            return result
    
    def _notify_kept_private(self, video_id: str, reason: str, status: VideoStatus):
        """Send notification that video was kept private."""
        print(f"[AutoPublish] Video {video_id} kept PRIVATE: {reason}")
        
        # Use existing email notification
        from email_notifier import send_email
        
        subject = f"[YouTube] Video Kept Private - {video_id}"
        body = f"""Auto-publish check completed for video {video_id}.

RESULT: Kept PRIVATE

REASON: {reason}

STATUS DETAILS:
- Upload Status: {status.upload_status}
- Processing Status: {status.processing_status}
- Issues: {', '.join(status.issues) if status.issues else 'None detected'}
- Warnings: {', '.join(status.warnings) if status.warnings else 'None'}

VIDEO URL: https://youtube.com/watch?v={video_id}

To manually publish after review:
    python publish_video.py {video_id}

NOTE: Content ID claims cannot be detected via API. Check YouTube Studio for claim status before publishing.
"""
        send_email(subject, body, ["jack_hui@msn.com"])
    
    def _notify_published(self, video_id: str, status: VideoStatus):
        """Send notification that video was auto-published."""
        print(f"[AutoPublish] Video {video_id} AUTO-PUBLISHED as {self.target_privacy}")
        
        from email_notifier import send_email
        
        subject = f"[YouTube] Video Auto-Published - {video_id}"
        body = f"""Auto-publish completed for video {video_id}.

RESULT: Published as {self.target_privacy.upper()}

VIDEO URL: https://youtube.com/watch?v={video_id}

STATUS CHECK:
- Upload Status: {status.upload_status}
- Processing Status: {status.processing_status}
- Issues: None detected
- Warnings: {', '.join(status.warnings) if status.warnings else 'None'}

NOTE: Content ID claims cannot be detected via API. If a claim appears later, you can:
1. Dispute the claim in YouTube Studio
2. Remove the video and regenerate
3. Edit the video to remove claimed content
"""
        send_email(subject, body, ["jack_hui@msn.com"])
    
    def _notify_error(self, video_id: str, error: Exception):
        """Send notification for auto-publish error."""
        print(f"[AutoPublish] Error checking {video_id}: {error}")
        
        from email_notifier import send_email
        
        subject = f"[YouTube] Auto-Publish Error - {video_id}"
        body = f"""Auto-publish check failed for video {video_id}.

ERROR: {str(error)}

VIDEO URL: https://youtube.com/watch?v={video_id}

The video remains PRIVATE. Please check manually.

To publish after manual review:
    python publish_video.py {video_id}
"""
        send_email(subject, body, ["jack_hui@msn.com"])


def check_video_status(video_id: str) -> VideoStatus:
    """
    Quick check of video status (no publish).
    
    Example:
        status = check_video_status("dQw4w9WgXcQ")
        print(f"Processed: {status.is_processed}, Clean: {status.is_clean}")
    """
    checker = AutoPublishChecker()
    return checker.get_video_status(video_id)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Check and auto-publish YouTube video")
    parser.add_argument("video_id", help="YouTube video ID to check")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Check status but don't publish")
    parser.add_argument("--status-only", action="store_true",
                       help="Just check status, don't wait or publish")
    args = parser.parse_args()
    
    checker = AutoPublishChecker()
    
    if args.status_only:
        print(f"Checking status for {args.video_id}...")
        status = checker.get_video_status(args.video_id)
        print(f"Upload Status: {status.upload_status}")
        print(f"Processing Status: {status.processing_status}")
        print(f"Privacy: {status.privacy_status}")
        print(f"Is Processed: {status.is_processed}")
        print(f"Is Clean: {status.is_clean}")
        if status.issues:
            print(f"Issues: {status.issues}")
        if status.warnings:
            print(f"Warnings: {status.warnings}")
    else:
        print(f"Running auto-publish check for {args.video_id}...")
        result = checker.check_and_publish(args.video_id, dry_run=args.dry_run)
        print(f"Published: {result.published}")
        print(f"Reason: {result.reason}")
        if result.status:
            print(f"Upload Status: {result.status.upload_status}")
            print(f"Processing Status: {result.status.processing_status}")
