import requests
from dotenv import load_dotenv
import time
import os

# Determine which .env file to load
env = os.getenv('ENV', 'development')
dotenv_path = f'.env.{env}'

# Load the environment variables from the chosen file
load_dotenv(dotenv_path=dotenv_path)

def create_media_container(ig_user_id, video_url, access_token):
    """
    Creates a media container on Instagram for the given video URL.
    """
    url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media"
    payload = {
        'media_type': 'REELS',
        'video_url': video_url,
        'access_token': access_token
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json().get('id')  # Return the container ID
    else:
        raise Exception(f"Failed to create media container: {response.text}")

def check_media_container_status(ig_user_id, container_id, access_token):
    """
    Checks the status of the media container to determine if it's ready for publishing.
    """
    url = f"https://graph.facebook.com/v20.0/{container_id}?fields=status,status_code&access_token={access_token}"
    response = requests.get(url)
    if response.status_code == 200:
        response_data = response.json()
        status_code = response_data.get('status_code')
        if status_code == 'ERROR':
            error_details = response_data
            print(f"Error details: {error_details}")  # Log detailed error information
        return status_code
    else:
        raise Exception(f"Failed to check media container status: {response.text}")

def publish_media(ig_user_id, container_id, access_token):
    """
    Publishes the media container to Instagram.
    """
    url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media_publish"
    payload = {
        'creation_id': container_id,
        'access_token': access_token
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json().get('id')  # Return the media ID
    else:
        raise Exception(f"Failed to publish media: {response.text}")

# Example usage
def publish_video_to_instagram(ig_user_id, video_url, access_token):
    """
    Publishes a video to Instagram by first creating a media container and then publishing it.
    """
    try:
        # Step 1: Create the media container
        print(f"Publishing video to Instagram from: {video_url}")
        container_id = create_media_container(ig_user_id, video_url, access_token)
        print(f"Media container created with ID: {container_id}")

        # Check if the container is ready before publishing
        retries = 5
        wait_time = 60  # seconds to wait between retries
        for _ in range(retries):
            status = check_media_container_status(ig_user_id, container_id, access_token)
            print(f"Container status: {status}")
            if status == 'FINISHED':
                # Step 2: Publish the container
                media_id = publish_media(ig_user_id, container_id, access_token)
                print(f"Video published to Instagram with media ID: {media_id}")
                return
            elif status == 'ERROR':
                # Break out of the loop if there is an error
                break
            else:
                print(f"Container not ready, status: {status}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        raise Exception("Failed to publish media after several retries. Container status remains: " + status)

    except Exception as e:
        print(str(e))

if __name__ == '__main__':
    # Provide the Instagram User ID, video URL, and access token
    ig_user_id = os.getenv("IG_USER_ID")
    video_url = 'https://ai-video-api.jackhui.com.au/tasks/test-task0001/final-1_converted.mp4'
    access_token = os.getenv("IG_ACCESS_TOKEN")

    # Call the function to publish the video
    publish_video_to_instagram(ig_user_id, video_url, access_token)