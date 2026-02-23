import os
from datetime import datetime

from dotenv import load_dotenv

from vetstoria.api import API

load_dotenv()

# Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

# Nova Sonic Model ID - can be "amazon.nova-sonic-v1:0" or "amazon.nova-2-sonic-v1:0"
MODEL_ID = os.getenv('NOVA_SONIC_MODEL_ID', 'amazon.nova-2-sonic-v1:0')
VOICE_ID = "tiffany"

FIRST_NAME = "AI-booking"
LAST_NAME = "AI-booking"
NAME = "AI-booking"
NOTES = "N/A"

SYSTEM_INSTRUCTION_VOICE = (f"""
You are a helpful voice AI assistant.
        """
)

# Audio configuration
INPUT_SAMPLE_RATE = 24000  # Nova Sonic expects 16kHz input
OUTPUT_SAMPLE_RATE = 24000  # Nova Sonic outputs 24kHz
CHANNELS = 1  # Mono
CHUNK_SIZE = 1024  # Typical chunk size for audio streaming

# Event types for Nova Sonic bidirectional streaming
EVENT_SESSION_START = "sessionStart"
EVENT_CONTENT_START = "contentStart"
EVENT_CONTENT_END = "contentEnd"
EVENT_TEXT_INPUT = "textInput"
EVENT_AUDIO_INPUT = "audioInput"
EVENT_AUDIO_OUTPUT = "audioOutput"
EVENT_TEXT_OUTPUT = "textOutput"
EVENT_TOOL_USE = "toolUse"
EVENT_TOOL_RESULT = "toolResult"

# Media types
MEDIA_TYPE_AUDIO = "audio/lpcm"
MEDIA_TYPE_TEXT = "text/plain"

# Roles
ROLE_USER = "USER"
ROLE_SYSTEM = "SYSTEM"
ROLE_ASSISTANT = "ASSISTANT"
