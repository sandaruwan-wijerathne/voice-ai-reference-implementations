"""
Audio processing utilities for noise reduction using spectral gating.
"""
import base64
import numpy as np
import noisereduce as nr
from typing import Optional


def process_audio_with_spectral_gating(
    base64_audio: str,
    sample_rate: int = 24000,
    stationary: bool = False,
    prop_decrease: float = 0.8,
) -> str:
    """
    Process audio with spectral gating using noisereduce to reduce noise.
    
    Args:
        base64_audio: Base64-encoded audio data (PCM16, 24kHz, mono)
        sample_rate: Sample rate of the audio (default: 24000 for OpenAI Realtime API)
        stationary: If True, uses stationary noise reduction (better for consistent noise)
                   If False, uses non-stationary reduction (better for varying noise)
        prop_decrease: Proportion of noise to reduce (0.0 to 1.0, default: 0.8)
    
    Returns:
        Base64-encoded processed audio data
    """
    try:
        # Decode base64 audio to bytes
        audio_bytes = base64.b64decode(base64_audio)
        
        # Convert bytes to numpy array (int16, little-endian)
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Convert to float32 for processing (normalize to [-1, 1])
        audio_float = audio_array.astype(np.float32) / 32768.0
        
        # Apply spectral gating noise reduction
        reduced_noise = nr.reduce_noise(
            y=audio_float,
            sr=sample_rate,
            stationary=stationary,
            prop_decrease=prop_decrease,
        )
        
        # Convert back to int16
        processed_audio = (reduced_noise * 32768.0).astype(np.int16)
        
        # Convert back to bytes (little-endian)
        processed_bytes = processed_audio.tobytes()
        
        # Encode back to base64
        processed_base64 = base64.b64encode(processed_bytes).decode('utf-8')
        
        return processed_base64
    
    except Exception as e:
        # If processing fails, return original audio
        print(f"Error processing audio with spectral gating: {e}")
        return base64_audio


def reduce_gain_pcm(
    base64_audio: str,
    gain_factor: float = 0.5,
    sample_rate: int = 24000,
) -> str:
    """
    Reduce the gain of 24000Hz PCM data chunks using numpy.
    
    Args:
        base64_audio: Base64-encoded audio data (PCM16, 24kHz, mono)
        gain_factor: Gain reduction factor (0.0 to 1.0, default: 0.5 for -6dB)
                     Values < 1.0 reduce gain, values > 1.0 increase gain
        sample_rate: Sample rate of the audio (default: 24000)
    
    Returns:
        Base64-encoded processed audio data
    """
    try:
        # Decode base64 audio to bytes
        audio_bytes = base64.b64decode(base64_audio)
        
        # Convert bytes to numpy array (int16, little-endian)
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Convert to float32 for processing (normalize to [-1, 1])
        audio_float = audio_array.astype(np.float32) / 32768.0
        
        # Apply gain reduction
        audio_float *= gain_factor
        
        # Clip to prevent overflow
        audio_float = np.clip(audio_float, -1.0, 1.0)
        
        # Convert back to int16
        processed_audio = (audio_float * 32768.0).astype(np.int16)
        
        # Convert back to bytes (little-endian)
        processed_bytes = processed_audio.tobytes()
        
        # Encode back to base64
        processed_base64 = base64.b64encode(processed_bytes).decode('utf-8')
        
        return processed_base64
    
    except Exception as e:
        # If processing fails, return original audio
        print(f"Error reducing gain: {e}")
        return base64_audio


def should_process_audio_event(event: dict) -> bool:
    """
    Check if an event contains audio data that should be processed.
    
    Args:
        event: Event dictionary from the input stream
    
    Returns:
        True if the event contains audio data to process
    """
    return (
        isinstance(event, dict) and
        event.get("type") == "input_audio_buffer.append" and
        "audio" in event and
        isinstance(event["audio"], str)
    )
