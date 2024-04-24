# voice_manager.py

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
    {"name": "en-US-SteffanNeural", "gender": "Male"}
]

# Function to get a random voice ensuring it is not the same as the last one used
def get_random_voice(last_voice=None):
    available_voices = [voice for voice in voices if voice['name'] != last_voice]
    selected_voice = random.choice(available_voices)
    return selected_voice
