# youtube_manager.py

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import os
import pickle
import re


def sanitize_title(title):
    """
    Sanitizes a video title by removing or replacing characters that might be problematic and ensures it does not exceed 100 characters.

    Args:
    title (str): The original title of the video.

    Returns:
    str: A sanitized version of the title.
    """
    if not title:
        return "Default Title"  # Provide a default title if none is provided

    # Remove leading and trailing whitespace
    title = title.strip()

    # Remove hashtags and other problematic special characters, replace with space
    title = re.sub(r"[#]", " ", title)  # Handles hashtags specifically
    title = re.sub(r"[^\w\s\-,.]", " ", title)  # Removes any character not a word, space, hyphen, or specified punctuation

    # Replace multiple spaces or underscores with a single space
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"_+", " ", title)

    # Trim spaces from the beginning and end of the title
    title = title.strip()

    # Truncate the title to 100 characters if longer
    if len(title) > 100:
        title = title[:100].rstrip()  # Truncate and remove any trailing spaces after cutting

    # Ensure the title is not empty after sanitization
    if not title:
        return "Default Title"

    return title


def authenticate_youtube(force_readonly=False):
    """
    Authenticate with YouTube API.
    
    Args:
        force_readonly: If True, use readonly scope (for status checks only)
        
    Returns:
        Authenticated YouTube service object
    """
    # Define the scopes required by the application.
    # youtube.force-ssl covers upload, status/list checks, and privacy updates.
    # youtube.upload alone cannot call videos.update(part=status).
    scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]

    # Path to your client_secrets.json file
    client_secrets_file = os.path.join(os.path.dirname(__file__), "client_secrets.json")

    # Path to the credentials file
    credentials_path = "youtube_credentials.pickle"
    credentials = None

    # Load saved credentials from a file if it exists
    if os.path.exists(credentials_path):
        with open(credentials_path, "rb") as token:
            credentials = pickle.load(token)

    # Check if the loaded credentials are still valid and include the required scopes.
    # Existing pickles do not automatically gain newly requested scopes on refresh.
    has_required_scopes = bool(credentials and credentials.has_scopes(scopes))
    if not credentials or not credentials.valid or not has_required_scopes:
        if credentials and credentials.expired and credentials.refresh_token and has_required_scopes:
            # Refresh the access token automatically if possible
            credentials.refresh(Request())
        else:
            raise RuntimeError(
                "YouTube OAuth reauthorization required: youtube_credentials.pickle "
                "does not include youtube.force-ssl scope. Run the manual reauth flow."
            )

    # Build the service object.
    youtube = build("youtube", "v3", credentials=credentials)
    return youtube


def upload_video(youtube, video_file, title, description, tags, privacy_status=None):
    """
    Upload a video to YouTube.
    
    Args:
        youtube: Authenticated YouTube service object
        video_file: Path to the video file
        title: Video title
        description: Video description
        tags: List of tags
        privacy_status: One of "private", "unlisted", or "public"
                       Defaults to YOUTUBE_DEFAULT_PRIVACY env var or "private"
    
    Returns:
        YouTube API response dict with video ID
    """
    if not video_file or not os.path.exists(video_file):
        raise FileNotFoundError("The video file path must be specified and the file must exist.")

    print(f"Original title: {title}")
    sanitized_title = sanitize_title(title)  # Sanitize the title

    if not sanitized_title or sanitized_title == "Default Title":
        print("Warning: Title fell back to default due to empty or invalid sanitization result.")

    print(f"Sanitized title: {sanitized_title}")

    # Determine privacy status - default to private for safety
    if privacy_status is None:
        privacy_status = os.getenv("YOUTUBE_DEFAULT_PRIVACY", "private").lower()
    
    # Validate privacy status
    valid_privacy = ["private", "unlisted", "public"]
    if privacy_status not in valid_privacy:
        print(f"Warning: Invalid privacy status {privacy_status}, defaulting to private")
        privacy_status = "private"
    
    print(f"Privacy status: {privacy_status}")

    body = {
        "snippet": {
            "title": sanitized_title,
            "description": description,
            "tags": tags,
            "categoryId": "28"  # This is the category for science
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }
    media = MediaFileUpload(video_file, mimetype="video/*")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    response = request.execute()
    return response


def update_video_privacy(youtube, video_id, privacy_status):
    """
    Update the privacy status of an existing video.
    
    Args:
        youtube: Authenticated YouTube service object
        video_id: YouTube video ID
        privacy_status: One of "private", "unlisted", or "public"
    
    Returns:
        YouTube API response
    """
    valid_privacy = ["private", "unlisted", "public"]
    if privacy_status not in valid_privacy:
        raise ValueError(f"Invalid privacy status: {privacy_status}. Must be one of {valid_privacy}")
    
    body = {
        "id": video_id,
        "status": {
            "privacyStatus": privacy_status
        }
    }
    
    request = youtube.videos().update(
        part="status",
        body=body
    )
    response = request.execute()
    print(f"Updated video {video_id} privacy to: {privacy_status}")
    return response


def get_video_status(youtube, video_id):
    """
    Get the processing and upload status of a video.
    
    Args:
        youtube: Authenticated YouTube service object
        video_id: YouTube video ID
    
    Returns:
        Dict with status info:
        {
            "video_id": str,
            "upload_status": str,  # deleted, failed, processed, rejected, uploaded
            "processing_status": str,  # processing, succeeded, failed, terminated
            "privacy_status": str,  # private, unlisted, public
            "rejection_reason": str or None,
            "failure_reason": str or None,
            "embeddable": bool,
            "license": str,
            "public_stats_viewable": bool,
        }
    """
    request = youtube.videos().list(
        part="status,processingDetails,contentDetails",
        id=video_id
    )
    response = request.execute()
    
    if not response.get("items"):
        raise ValueError(f"Video not found: {video_id}")
    
    item = response["items"][0]
    status_data = item.get("status", {})
    processing_data = item.get("processingDetails", {})
    
    return {
        "video_id": video_id,
        "upload_status": status_data.get("uploadStatus", ""),
        "processing_status": processing_data.get("processingStatus", ""),
        "privacy_status": status_data.get("privacyStatus", ""),
        "rejection_reason": status_data.get("rejectionReason"),
        "failure_reason": status_data.get("failureReason"),
        "embeddable": status_data.get("embeddable", True),
        "license": status_data.get("license", ""),
        "public_stats_viewable": status_data.get("publicStatsViewable", True),
    }
