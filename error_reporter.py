"""
Centralized error reporting for YouTube Uploader pipeline.
Sends email notifications for failures and provides structured error logging.
"""

import os
import traceback
from datetime import datetime
from email_notifier import send_email
from dotenv import load_dotenv

# Load environment
env = os.getenv("ENV", "development")
load_dotenv(dotenv_path=f".env.{env}")

# Error categories for better diagnosis
ERROR_CATEGORIES = {
    "TOKEN_EXPIRED": {
        "patterns": ["Session has expired", "Error validating access token", "OAuthException"],
        "action": "Instagram token has expired. Generate a new token at https://developers.facebook.com/tools/explorer/ and update IG_ACCESS_TOKEN in .env.production",
        "severity": "critical"
    },
    "API_RATE_LIMIT": {
        "patterns": ["rate limit", "too many requests", "429"],
        "action": "API rate limit hit. Wait and retry, or reduce request frequency.",
        "severity": "warning"
    },
    "VIDEO_GENERATION_FAILED": {
        "patterns": ["Task failed", "progress information is missing", "Error in generating video"],
        "action": "Video generation API failed. Check ai-video-api.jackhui.com.au status.",
        "severity": "error"
    },
    "NETWORK_ERROR": {
        "patterns": ["ConnectionError", "Timeout", "Connection refused"],
        "action": "Network connectivity issue. Check internet connection and API endpoints.",
        "severity": "error"
    },
    "YOUTUBE_AUTH_FAILED": {
        "patterns": ["YouTube", "credentials", "pickle", "authentication"],
        "action": "YouTube authentication failed. Re-run OAuth flow to refresh credentials.",
        "severity": "critical"
    },
    "INSTAGRAM_UPLOAD_FAILED": {
        "patterns": ["Failed to create media container", "Failed to publish media"],
        "action": "Instagram upload failed. Check video format and token validity.",
        "severity": "error"
    }
}

def categorize_error(error_message: str) -> dict:
    """Categorize an error based on known patterns."""
    error_str = str(error_message).lower()
    for category, info in ERROR_CATEGORIES.items():
        for pattern in info["patterns"]:
            if pattern.lower() in error_str:
                return {
                    "category": category,
                    "action": info["action"],
                    "severity": info["severity"]
                }
    return {
        "category": "UNKNOWN",
        "action": "Unknown error. Check logs for details.",
        "severity": "error"
    }

def format_error_report(
    stage: str,
    error: Exception,
    context: dict = None
) -> str:
    """Format a detailed error report."""
    error_info = categorize_error(str(error))
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    report = f"""
================================================================================
ERROR REPORT - YouTube Uploader Pipeline
================================================================================
Timestamp: {timestamp}
Stage: {stage}
Severity: {error_info["severity"].upper()}
Category: {error_info["category"]}

ERROR MESSAGE:
{str(error)}

RECOMMENDED ACTION:
{error_info["action"]}
"""
    
    if context:
        report += "\nCONTEXT:\n"
        for key, value in context.items():
            # Truncate long values and mask tokens
            value_str = str(value)
            if "token" in key.lower() or "secret" in key.lower():
                value_str = value_str[:10] + "..." if len(value_str) > 10 else "***"
            elif len(value_str) > 200:
                value_str = value_str[:200] + "..."
            report += f"  {key}: {value_str}\n"
    
    report += f"\nSTACK TRACE:\n{traceback.format_exc()}"
    report += "\n================================================================================"
    
    return report

def report_error(
    stage: str,
    error: Exception,
    context: dict = None,
    send_email_notification: bool = True
) -> None:
    """
    Report an error with logging and optional email notification.
    
    Args:
        stage: Pipeline stage where error occurred (e.g., "Instagram Upload", "Video Generation")
        error: The exception that was raised
        context: Additional context dict (video_subject, urls, etc.)
        send_email_notification: Whether to send email alert
    """
    report = format_error_report(stage, error, context)
    
    # Always log to stdout (captured by cron)
    print(report)
    
    # Send email for critical/error severity
    error_info = categorize_error(str(error))
    if send_email_notification and error_info["severity"] in ["critical", "error"]:
        subject = f"[{error_info['severity'].upper()}] YouTube Uploader - {stage} Failed"
        send_email(subject, report, ["jack_hui@msn.com"])
        print(f"Error notification email sent for: {stage}")

def report_success(stage: str, details: dict = None) -> None:
    """Log a success message with optional details."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    msg = f"[{timestamp}] SUCCESS: {stage}"
    if details:
        for key, value in details.items():
            msg += f"\n  {key}: {value}"
    print(msg)

def create_run_summary(results: dict) -> str:
    """Create a summary of the pipeline run."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    summary = f"""
================================================================================
PIPELINE RUN SUMMARY - {timestamp}
================================================================================
"""
    
    for stage, result in results.items():
        status = "✅ SUCCESS" if result.get("success") else "❌ FAILED"
        summary += f"\n{stage}: {status}"
        if result.get("details"):
            summary += f" - {result[details]}"
        if result.get("error"):
            summary += f"\n   Error: {result[error][:100]}..."
    
    summary += "\n================================================================================"
    return summary
