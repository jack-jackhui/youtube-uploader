# video_api_call.py

import requests
import os
import re
import time
import unidecode
def generate_video_script(api_key, api_host, video_subject, video_language='en', paragraph_number=1):
    api_url = f'{api_host}/api/v1/scripts'
    #print("Access Token is", access_token)
    headers = {'X-API-Key': api_key}
    payload = {
        "video_subject": video_subject,
        "video_language": video_language,
        "paragraph_number": paragraph_number
    }
    response = requests.post(api_url, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json().get('data')
        if data:
            video_script = data.get('video_script')
            return video_script
        else:
            raise Exception("No data available in the response.")
    else:
        raise Exception(f"Error: {response.status_code} - {response.json().get('message')}")


def generate_video_terms(api_key, api_host, video_subject, video_script, amount, video_language='en'):
    api_url = f'{api_host}/api/v1/terms'
    headers = {'X-API-Key': api_key}
    payload = {
        "video_subject": video_subject,
        "video_language": video_script,
        "amount": amount,
        "video_language": video_language
    }
    response = requests.post(api_url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json().get('data')
        if data:
            video_terms = data.get('video_terms')
            return video_terms
        else:
            raise Exception("No data available in the response.")
    else:
        raise Exception(f"Error: {response.status_code} - {response.json().get('message')}")

def generate_video(api_key, api_host, video_subject, video_script, video_terms, voice_name, video_aspect="9:16",
                   video_concat_mode="random", video_clip_duration=5, video_count=1, video_language="",
                   voice_volume=1, bgm_type="random", bgm_file="", bgm_volume=0.2,
                   subtitle_enabled=True, subtitle_position="bottom", font_name="STHeitiMedium.ttc",
                   text_fore_color="#FFFFFF", text_background_color="transparent", font_size=60,
                   stroke_color="#000000", stroke_width=1.5, n_threads=2, paragraph_number=1):
    api_url = f'{api_host}/api/v1/videos'
    headers = {'X-API-Key': api_key}
    payload = {
        "video_subject": video_subject,
        "video_script": video_script,
        "video_terms": video_terms,
        "video_aspect": video_aspect,
        "video_concat_mode": video_concat_mode,
        "video_clip_duration": video_clip_duration,
        "video_count": video_count,
        "video_language": video_language,
        "voice_name": voice_name,
        "voice_volume": voice_volume,
        "bgm_type": bgm_type,
        "bgm_file": bgm_file,
        "bgm_volume": bgm_volume,
        "subtitle_enabled": subtitle_enabled,
        "subtitle_position": subtitle_position,
        "font_name": font_name,
        "text_fore_color": text_fore_color,
        "text_background_color": text_background_color,
        "font_size": font_size,
        "stroke_color": stroke_color,
        "stroke_width": stroke_width,
        "n_threads": n_threads,
        "paragraph_number": paragraph_number
    }
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()  # This will raise an exception for HTTP errors
        task_id = response.json()['data']['task_id']
        download_url = f"{api_host}/tasks/{task_id}/final-1.mp4"
        converted_video_url = f"{api_host}/tasks/{task_id}/final-1_converted.mp4"

        # Return the appropriate video URLs
        return {
            "original": download_url,
            "converted": converted_video_url
        }
    except requests.exceptions.HTTPError as err:
        # Handles HTTP errors that raise_for_status might throw
        print(f"HTTP error occurred: {err} - Status code: {response.status_code}")
        print(response.text)
    except Exception as e:
        # Handles any other exceptions
        print(f"An error occurred: {e}")

def check_task_status(api_key, api_url, task_id):
    """
    Polls the task status endpoint until the video generation task is complete.

    Args:
    access_token (str): API access token for authorization.
    api_url (str): Base URL of the API.
    task_id (str): ID of the task to check status for.

    Returns:
    bool: True if the task is completed successfully, False otherwise.
    """
    status_url = f"{api_url}/api/v1/tasks/{task_id}"
    headers = {'X-API-Key': api_key}

    try:
        while True:
            response = requests.get(status_url, headers=headers)
            response.raise_for_status()  # Will raise an exception for HTTP errors
            result = response.json()

            if result['data']['progress'] == 100:
                print("Task completed successfully.")
                return True
            elif 'progress' in result['data']:
                print(f"Task progress: {result['data']['progress']}%")
                time.sleep(10)  # Sleep for 10 seconds before polling again
            else:
                print("Task progress information is missing.")
                return False
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err} - Status code: {response.status_code}")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def sanitize_filename(filename):
    """Sanitizes a string to be safe for use as a filename."""
    # Remove double quotes and other special characters except for alphanumeric, underscores, hyphens, and periods
    sanitized = re.sub(r'[^\w\-.]', '_', filename)
    # Convert any non-ASCII characters (e.g., Chinese) to their closest ASCII equivalent
    sanitized = unidecode.unidecode(sanitized)
    return sanitized

def download_video(video_url, video_subject, save_path="downloaded_videos"):
    """
    Downloads a video from a given URL, using the video subject as the filename, and saves it to a specified path.

    Args:
    video_url (str): URL of the video to download.
    video_subject (str): Subject of the video to use as the filename.
    save_path (str): Local directory path where the video will be saved.

    Returns:
    str: Path to the downloaded video file.
    """
    if not os.path.exists(save_path):
        os.makedirs(save_path)  # Create the directory if it does not exist

    # Sanitize the video_subject to create a safe filename
    safe_filename = sanitize_filename(video_subject) + ".mp4"
    local_filename = os.path.join(save_path, safe_filename)

    try:
        with requests.get(video_url, stream=True) as r:
            r.raise_for_status()  # Check that the request was successful
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):  # Download the file in chunks
                    f.write(chunk)
        return local_filename
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err} - Status code: {r.status_code}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None