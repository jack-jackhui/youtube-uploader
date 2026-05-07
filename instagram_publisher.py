"""
Instagram video publisher using Facebook Graph API.
Handles media container creation, status polling, and publishing.
"""

import requests
from dotenv import load_dotenv
import time
import os
import json

# Determine which .env file to load
env = os.getenv("ENV", "development")
dotenv_path = f".env.{env}"
load_dotenv(dotenv_path=dotenv_path)


class InstagramPublishError(Exception):
    """Custom exception for Instagram publishing errors."""
    def __init__(self, message, error_type=None, error_code=None, is_token_error=False):
        super().__init__(message)
        self.error_type = error_type
        self.error_code = error_code
        self.is_token_error = is_token_error


def parse_api_error(response_text: str) -> dict:
    """Parse Facebook API error response."""
    try:
        data = json.loads(response_text)
        error = data.get("error", {})
        return {
            "message": error.get("message", response_text),
            "type": error.get("type"),
            "code": error.get("code"),
            "error_subcode": error.get("error_subcode"),
            "is_token_error": error.get("code") == 190  # OAuth errors
        }
    except json.JSONDecodeError:
        return {
            "message": response_text,
            "type": None,
            "code": None,
            "is_token_error": False
        }


def create_media_container(ig_user_id, video_url, access_token, caption=None):
    """
    Creates a media container on Instagram for the given video URL.
    
    Raises:
        InstagramPublishError: If container creation fails
    """
    url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "access_token": access_token
    }
    if caption:
        payload["caption"] = caption[:2200]
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        container_id = response.json().get("id")
        if container_id:
            return container_id
        raise InstagramPublishError("No container ID in response", error_type="MISSING_ID")
    
    error_info = parse_api_error(response.text)
    raise InstagramPublishError(
        f"Failed to create media container: {error_info['message']}",
        error_type=error_info["type"],
        error_code=error_info["code"],
        is_token_error=error_info["is_token_error"]
    )


def check_media_container_status(container_id, access_token):
    """
    Checks the status of the media container.
    
    Returns:
        tuple: (status_code, error_message or None)
    """
    url = f"https://graph.facebook.com/v20.0/{container_id}?fields=status,status_code&access_token={access_token}"
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        status_code = data.get("status_code")
        error_msg = None
        
        if status_code == "ERROR":
            error_msg = data.get("status", "Unknown error during processing")
            
        return status_code, error_msg
    
    error_info = parse_api_error(response.text)
    raise InstagramPublishError(
        f"Failed to check container status: {error_info['message']}",
        error_type=error_info["type"],
        error_code=error_info["code"],
        is_token_error=error_info["is_token_error"]
    )


def publish_media(ig_user_id, container_id, access_token):
    """
    Publishes the media container to Instagram.
    
    Returns:
        str: The published media ID
        
    Raises:
        InstagramPublishError: If publishing fails
    """
    url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media_publish"
    payload = {
        "creation_id": container_id,
        "access_token": access_token
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        media_id = response.json().get("id")
        if media_id:
            return media_id
        raise InstagramPublishError("No media ID in publish response", error_type="MISSING_ID")
    
    error_info = parse_api_error(response.text)
    raise InstagramPublishError(
        f"Failed to publish media: {error_info['message']}",
        error_type=error_info["type"],
        error_code=error_info["code"],
        is_token_error=error_info["is_token_error"]
    )


def publish_video_to_instagram(ig_user_id, video_url, access_token, caption=None, max_retries=5, retry_wait=60):
    """
    Publishes a video to Instagram Reels.
    
    Args:
        ig_user_id: Instagram user ID
        video_url: Public URL of the video to upload
        access_token: Facebook Graph API access token
        max_retries: Maximum status check retries
        retry_wait: Seconds between status checks
        
    Returns:
        tuple: (success: bool, result: dict)
            result contains either {"media_id": "..."} or {"error": "...", "is_token_error": bool}
    """
    context = {
        "video_url": video_url,
        "ig_user_id": ig_user_id
    }
    
    try:
        # Step 1: Create media container
        print(f"[Instagram] Creating media container for: {video_url}")
        container_id = create_media_container(ig_user_id, video_url, access_token, caption=caption)
        print(f"[Instagram] Container created: {container_id}")
        context["container_id"] = container_id
        
        # Step 2: Poll for container readiness
        for attempt in range(1, max_retries + 1):
            status, error_msg = check_media_container_status(container_id, access_token)
            print(f"[Instagram] Container status (attempt {attempt}/{max_retries}): {status}")
            
            if status == "FINISHED":
                # Step 3: Publish
                media_id = publish_media(ig_user_id, container_id, access_token)
                print(f"[Instagram] Published successfully! Media ID: {media_id}")
                return True, {"media_id": media_id}
                
            elif status == "ERROR":
                raise InstagramPublishError(
                    f"Container processing failed: {error_msg}",
                    error_type="PROCESSING_ERROR"
                )
                
            elif status == "IN_PROGRESS":
                print(f"[Instagram] Still processing, waiting {retry_wait}s...")
                time.sleep(retry_wait)
            else:
                print(f"[Instagram] Unknown status {status}, waiting {retry_wait}s...")
                time.sleep(retry_wait)
        
        # Max retries exceeded
        raise InstagramPublishError(
            f"Container did not finish after {max_retries} attempts (last status: {status})",
            error_type="TIMEOUT"
        )
        
    except InstagramPublishError as e:
        error_result = {
            "error": str(e),
            "error_type": e.error_type,
            "error_code": e.error_code,
            "is_token_error": e.is_token_error,
            "context": context
        }
        
        # Log with clear indication of token errors
        if e.is_token_error:
            print(f"[Instagram] TOKEN ERROR: {e}")
            print("[Instagram] ACTION REQUIRED: Generate new token at https://developers.facebook.com/tools/explorer/")
        else:
            print(f"[Instagram] ERROR: {e}")
            
        return False, error_result
        
    except Exception as e:
        error_result = {
            "error": str(e),
            "error_type": "UNEXPECTED",
            "is_token_error": False,
            "context": context
        }
        print(f"[Instagram] UNEXPECTED ERROR: {e}")
        return False, error_result


if __name__ == "__main__":
    # Test mode
    ig_user_id = os.getenv("IG_USER_ID")
    access_token = os.getenv("IG_ACCESS_TOKEN")
    video_url = "https://ai-video-api.jackhui.com.au/tasks/test-task0001/final-1_converted.mp4"
    
    success, result = publish_video_to_instagram(ig_user_id, video_url, access_token)
    print(f"\nResult: success={success}, result={result}")
