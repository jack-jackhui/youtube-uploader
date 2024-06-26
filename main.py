# main.py

import video_api_call
import youtube_manager
# import google_sheets
import openai_chatgpt
import voice_manager
import json
from dotenv import load_dotenv
import os
import test_youtube

# Determine which .env file to load
env = os.getenv('ENV', 'development')
dotenv_path = f'.env.{env}'

# Load the environment variables from the chosen file
load_dotenv(dotenv_path=dotenv_path)


# Now you can access these variables using os.getenv
api_host = os.getenv('API_HOST')
api_key = os.getenv('API_KEY')

openai_api_key = os.getenv('OPEN_AI_KEY')  # Retrieve securely

def main():

    # Load the last used voice if available
    try:
        with open('last_voice.json', 'r') as file:
            last_voice = json.load(file).get('last_voice_name')
    except (FileNotFoundError, json.JSONDecodeError):
        last_voice = None

    # Get a new random voice, not repeating the last one
    voice = voice_manager.get_random_voice(last_voice)
    voice_name = voice['name']

    # Store the current voice as the last used for next time
    with open('last_voice.json', 'w') as file:
        json.dump({'last_voice_name': voice_name}, file)

    predefined_prompt = "Act as a social media influencer, generate a single creative and engaging " \
                        "one line video subject for a tech-themed YouTube channel, ensure the video subject " \
                        "focused on one of the following topics: " \
                        "AI,Defi,ChatGPT, blockchain, Bitcoin, Ethereum, Solana or Algorand." \
                        "Rotate between these topics frequently, but do not write more than one " \
                        "topics in a single video subject. Limit the number of characters to 100 or less."

    # Generate video subject using OpenAI's ChatGPT
    print("Generating video subject...")
    video_subject = openai_chatgpt.generate_video_subject(openai_api_key, predefined_prompt)
    print(f"Video Subject: {video_subject}")

    video_keyword_amt = 5

    if video_subject:
        video_script = video_api_call.generate_video_script(api_key, api_host, video_subject, '', 1)
        print(f"Video Script: {video_script}")
        video_terms = video_api_call.generate_video_terms(api_key,api_host, video_subject, video_script, video_keyword_amt)
        print(f"Video Keywords: {video_terms}")

        # Handle potential NoneType for video_terms
        if video_terms:
            tags = video_terms
        else:
            tags = ["Future Tech", "tags"]


    print("Generating video...")
    #print(f"Video Script: {video_script}")
    #print(f"Video Keywords: {video_terms}")
    video_url = video_api_call.generate_video(api_key, api_host, video_subject, video_script, video_terms, voice_name=voice_name)

    # Extract the task ID from the URL
    if video_url:
        task_id = video_url.split('/')[-2]
    else:
        print("Failed to obtain video URL")
        return

    # Check the status of the video generation task
    if video_api_call.check_task_status(api_key, api_host, task_id):
        # Once completed, download the video
        downloaded_file = video_api_call.download_video(video_url, video_subject)
        if downloaded_file:
            print(f"Video downloaded successfully: {downloaded_file}")
        else:
            print("Failed to download video.")
    else:
        print("Video generation task failed or was incomplete.")

    print("Authenticating with YouTube...")
    youtube = youtube_manager.authenticate_youtube()

    print("Uploading video to YouTube...")
    upload_response = youtube_manager.upload_video(youtube, downloaded_file, video_subject, video_subject, tags)

    print("Video uploaded successfully. Video ID:", upload_response['id'])

if __name__ == '__main__':
    # Uncomment the line below to test YouTube upload functionality independently.
    #test_youtube.test_youtube_upload()

    main()
