# openai_chatgpt.py

import os
from openai import OpenAI

def generate_video_subject(api_key, prompt):
    client = OpenAI(api_key=api_key)  # Setup the client with your API key

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-3.5-turbo",  # Specify the model here, adjust if needed
        )
        # Extracting the content from the completion response
        subject = chat_completion.choices[0].message.content
        return subject.strip()
    except Exception as e:
        print(f"Failed to generate video subject: {str(e)}")
        return None
