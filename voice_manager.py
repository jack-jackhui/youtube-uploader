# voice_manager.py
import json
import random

# List of voices
voices = [
    {"name": "en-US-AnaNeural", "gender": "Female"},
    {"name": "en-US-AndrewNeural", "gender": "Male"},
    {"name": "en-US-AriaNeural", "gender": "Female"},
    {"name": "en-US-AvaNeural", "gender": "Female"},
    {"name": "en-US-BrianNeural", "gender": "Male"},
    {"name": "en-US-ChristopherNeural", "gender": "Male"},
    {"name": "en-US-EmmaNeural", "gender": "Female"},
    {"name": "en-US-EricNeural", "gender": "Male"},
    {"name": "en-US-GuyNeural", "gender": "Male"},
    {"name": "en-US-JennyNeural", "gender": "Female"},
    {"name": "en-US-MichelleNeural", "gender": "Female"},
    {"name": "en-US-RogerNeural", "gender": "Male"},
    {"name": "en-US-SteffanNeural", "gender": "Male"},
    {"name": "zh-CN-XiaoxiaoNeural", "gender": "Female"},
    {"name": "zh-CN-XiaoyiNeural", "gender": "Female"},
    {"name": "zh-CN-YunjianNeural", "gender": "Male"},
    {"name": "zh-CN-YunxiNeural", "gender": "Male"},
    {"name": "zh-CN-YunxiaNeural", "gender": "Male"},
    {"name": "zh-CN-YunyangNeural", "gender": "Male"},
    {"name": "zh-CN-liaoning-XiaobeiNeural", "gender": "Female"},
    {"name": "zh-CN-shaanxi-XiaoniNeural", "gender": "Female"}
]

# Function to get a random voice ensuring it is not the same as the last one used
def get_random_voice(last_voice=None, language="en"):
    # language_voices = [voice for voice in voices if voice['language'] == language]

    # Filter voices by extracting language from the 'name' field
    language_voices = [voice for voice in voices if voice['name'].startswith(f"{language}-")]

    available_voices = [voice for voice in language_voices if voice['name'] != last_voice]
    if not available_voices:
        # If all voices have been used, reset the list
        available_voices = language_voices

    selected_voice = random.choice(available_voices)
    return selected_voice['name']

def get_last_used_voice(language="en"):
    try:
        with open('last_voice.json', 'r') as file:
            last_voice_data = json.load(file)
            return last_voice_data.get(f'last_voice_name_{language}')
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def store_last_used_voice(voice_name, language="en"):
    try:
        with open('last_voice.json', 'r') as file:
            last_voice_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        last_voice_data = {}
    last_voice_data[f'last_voice_name_{language}'] = voice_name
    with open('last_voice.json', 'w') as file:
        json.dump(last_voice_data, file)