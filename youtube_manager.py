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


def authenticate_youtube():
    # Define the scopes required by the application.
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]

    # Path to your client_secrets.json file
    client_secrets_file = os.path.join(os.path.dirname(__file__), "client_secrets.json")

    # Path to the credentials file
    credentials_path = "youtube_credentials.pickle"
    credentials = None

    # Load saved credentials from a file if it exists
    if os.path.exists(credentials_path):
        with open(credentials_path, "rb") as token:
            credentials = pickle.load(token)

    # Check if the loaded credentials are still valid
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            # Refresh the access token automatically if possible
            credentials.refresh(Request())
        else:
            # No valid credentials available, prompt user for authorization
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, scopes=scopes)
            credentials = flow.run_local_server(port=4000)

            # Save the credentials for the next run
            with open(credentials_path, "wb") as token:
                pickle.dump(credentials, token)

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
