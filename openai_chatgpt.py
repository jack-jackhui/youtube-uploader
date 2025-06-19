# openai_chatgpt.py

import os
from openai import OpenAI
from openai import AzureOpenAI

def generate_video_subject(api_key, prompt):
    # client = OpenAI(api_key=api_key)  # Setup the client with your API key
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=os.getenv("AZURE_OPENAI_MODEL_NAME"),  # Specify the model here, adjust if needed
        )
        # Extracting the content from the completion response
        subject = chat_completion.choices[0].message.content
        return subject.strip()
    except Exception as e:
        print(f"Failed to generate video subject: {str(e)}")
        return None
