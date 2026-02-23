import asyncio
import json
import base64
import websockets
import numpy as np
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator, Any, Callable, Coroutine, Optional
from gemini_speech_to_speech.constants_gemini import SYSTEM_INSTRUCTION_VOICE

from .utils import amerge
from langchain_core.tools import BaseTool
from langchain_core._api import beta
from langchain_core.utils import secret_from_env

from pydantic import BaseModel, Field, SecretStr, PrivateAttr

# Try to import scipy for audio resampling
try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available. Audio resampling will be skipped. Install scipy for resampling support.")

# Import database functions for message exchange tracking
try:
    from database import create_message_exchange
    from utils.tools import current_conversation_id
    MESSAGE_TRACKING_AVAILABLE = True
except ImportError:
    MESSAGE_TRACKING_AVAILABLE = False
    print("Warning: Message tracking not available.")

# Import audio processing utilities
try:
    from utils.audio_processing import (
        process_audio_with_spectral_gating,
        should_process_audio_event,
    )
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    print("Warning: Audio processing utilities not available. Install noisereduce and numpy.")

# Import voice configuration
try:
    from ..constants_gemini import VOICE, MODEL
    DEFAULT_VOICE = VOICE
    DEFAULT_MODEL = MODEL
except ImportError:
    DEFAULT_VOICE = "Gacrux"  # Default fallback
    DEFAULT_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

# Gemini WebSocket URL
DEFAULT_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"

# Audio configuration
GEMINI_INPUT_SAMPLE_RATE = 16000  # Gemini input audio sample rate
GEMINI_OUTPUT_SAMPLE_RATE = 24000  # Gemini output audio sample rate
TARGET_SAMPLE_RATE = 24000  # Target sample rate for client


def resample_audio(audio_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
    """
    Resample audio from one sample rate to another.
    
    Args:
        audio_bytes: Raw PCM16 audio bytes (little-endian, mono)
        from_rate: Source sample rate
        to_rate: Target sample rate
    
    Returns:
        Resampled audio bytes (PCM16, little-endian, mono)
    """
    if not SCIPY_AVAILABLE:
        print("Warning: scipy not available, returning original audio without resampling")
        return audio_bytes
    
    try:
        # Convert bytes to numpy array (int16, little-endian)
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Convert to float32 for processing (normalize to [-1, 1])
        audio_float = audio_array.astype(np.float32) / 32768.0
        
        # Calculate the number of samples after resampling
        num_samples = len(audio_float)
        target_samples = int(num_samples * to_rate / from_rate)
        
        # Resample using scipy.signal.resample
        resampled_float = signal.resample(audio_float, target_samples)
        
        # Ensure values are in valid range [-1, 1]
        resampled_float = np.clip(resampled_float, -1.0, 1.0)
        
        # Convert back to int16
        resampled_int16 = (resampled_float * 32768.0).astype(np.int16)
        
        # Convert back to bytes (little-endian)
        resampled_bytes = resampled_int16.tobytes()
        
        return resampled_bytes
    
    except Exception as e:
        print(f"Error resampling audio: {e}, returning original audio")
        return audio_bytes


@asynccontextmanager
async def connect(*, api_key: str, model: str, url: str) -> AsyncGenerator[
    tuple[
        Callable[[dict[str, Any] | str], Coroutine[Any, Any, None]],
        AsyncIterator[dict[str, Any]],
    ],
    None,
]:
    """
    Connect to Gemini's WebSocket API for voice agents.
    
    Args:
        api_key: Gemini API key
        model: The model to use (e.g., "gemini-2.0-flash-exp")
        url: WebSocket URL
    """
    ws_url = f"{url}?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }

    model_setup = {
        "model": f"models/{model}",
        "generation_config": {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {"prebuilt_voice_config": {"voice_name": "Gacrux"}}
            },
        },
        "system_instruction": {
            "parts": [
                {
                    "text": SYSTEM_INSTRUCTION_VOICE,
                }
            ]
        } 
    }

    websocket = await websockets.connect(ws_url, additional_headers=headers)

    try:
        # Send setup message
        await websocket.send(json.dumps({"setup": model_setup}))
        # Wait for initial response
        await websocket.recv()
        print("Connected to Gemini, You can start talking now")
        
        async def send_event(event: dict[str, Any] | str) -> None:
            if isinstance(event, dict):
                formatted_event = json.dumps(event)
                await websocket.send(formatted_event)
            else:
                print("Sending event: ", event)
                await websocket.send(event)

        async def event_stream() -> AsyncIterator[dict[str, Any]]:
            async for message in websocket:
                try:
                    response = json.loads(message)
                    yield response
                except json.JSONDecodeError:
                    print(f"Error decoding message: {message}")
                    continue

        stream: AsyncIterator[dict[str, Any]] = event_stream()

        yield send_event, stream
    finally:
        await websocket.close()


class VoiceToolExecutor(BaseModel):
    """
    Can accept function calls and emits function call outputs to a stream.
    """

    tools_by_name: dict[str, BaseTool]
    _trigger_future: asyncio.Future = PrivateAttr(default_factory=asyncio.Future)
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _trigger_func(self) -> dict:  # returns a tool call
        return await self._trigger_future

    async def add_tool_call(self, tool_call: dict) -> None:
        # lock to avoid simultaneous tool calls racing
        async with self._lock:
            if self._trigger_future.done():
                # TODO: handle simultaneous tool calls better
                raise ValueError("Tool call adding already in progress")

            self._trigger_future.set_result(tool_call)

    async def _create_tool_call_task(self, tool_call: dict) -> asyncio.Task[dict]:
        tool = self.tools_by_name.get(tool_call["name"])
        if tool is None:
            # immediately yield error, do not add task
            raise ValueError(
                f"tool {tool_call['name']} not found. "
                f"Must be one of {list(self.tools_by_name.keys())}"
            )

        # try to parse args
        try:
            args = tool_call.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)
        except json.JSONDecodeError:
            raise ValueError(
                f"failed to parse arguments `{tool_call.get('arguments', {})}`. Must be valid JSON."
            )

        async def run_tool() -> dict:
            result = await tool.ainvoke(args)
            try:
                result_str = json.dumps(result) if not isinstance(result, str) else result
            except TypeError:
                # not json serializable, use str
                result_str = str(result)
            return {
                "type": "tool.result",
                "tool_call_id": tool_call.get("tool_call_id", tool_call.get("id")),
                "result": result_str,
            }

        task = asyncio.create_task(run_tool())
        return task

    async def output_iterator(self) -> AsyncIterator[dict]:  # yield events
        trigger_task = asyncio.create_task(self._trigger_func())
        tasks = set([trigger_task])
        while True:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                tasks.remove(task)
                if task == trigger_task:
                    async with self._lock:
                        self._trigger_future = asyncio.Future()
                    trigger_task = asyncio.create_task(self._trigger_func())
                    tasks.add(trigger_task)
                    tool_call = task.result()
                    try:
                        new_task = await self._create_tool_call_task(tool_call)
                        tasks.add(new_task)
                    except ValueError as e:
                        yield {
                            "type": "tool.result",
                            "tool_call_id": tool_call.get("tool_call_id", tool_call.get("id")),
                            "result": f"Error: {str(e)}",
                        }
                else:
                    yield task.result()


class GeminiVoiceReactAgent(BaseModel):
    model: str = Field(default=DEFAULT_MODEL)
    api_key: SecretStr = Field(
        alias="gemini_api_key",
        default_factory=secret_from_env("GEMINI_API_KEY", default=""),
    )
    instructions: str | None = None
    tools: list[BaseTool] | None = None
    url: str = Field(default=DEFAULT_URL)
    voice: str = Field(default=DEFAULT_VOICE)
    _model_speaking: bool = PrivateAttr(default=False)

    async def aconnect(
        self,
        input_stream: AsyncIterator[str],
        send_output_chunk: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Connect to the Gemini API and send and receive messages.

        input_stream: AsyncIterator[str]
            Stream of input events to send to the model. Usually transports audio data from the microphone.
        send_output_chunk: Callable[[str], None]
            Callback to receive output events from the model. Usually sends audio events to the speaker.
        """
        tools_by_name = {tool.name: tool for tool in (self.tools or [])}
        tool_executor = VoiceToolExecutor(tools_by_name=tools_by_name)
        
        # Track latest user input and AI response for message exchange
        latest_user_input: str | None = None
        latest_ai_response: str | None = None

        async with connect(
            api_key=self.api_key.get_secret_value(),
            model=self.model,
            url=self.url
        ) as (
            model_send,
            model_receive_stream,
        ):

            # Get the model to speak first
            await model_send( {"client_content": { "turns": [ {"role": "user", "parts": [{"text": "Hello!"}]} ], "turn_complete": True}})

            # Send initial instructions if provided
            # Note: Gemini may handle instructions differently - this is a placeholder
            # The actual implementation may need to send instructions in the setup or as a message
            
            async for stream_key, data_raw in amerge(
                input_mic=input_stream,
                output_speaker=model_receive_stream,
                tool_outputs=tool_executor.output_iterator(),
            ):
                # Parse data based on its type and stream source
                data = None
                
                if stream_key == "input_mic":
                    parsed_mic_data = json.loads(data_raw)
                    if isinstance(parsed_mic_data, dict):
                        data = parsed_mic_data
                    else:
                        print(f"unexpected input_mic data type: {type(data_raw)}, value: {data_raw}")
                        continue

                elif stream_key == "output_speaker":
                    # Output stream from model_receive_stream yields dicts
                    if isinstance(data_raw, dict):
                        data = data_raw
                    else:
                        print(f"unexpected output_speaker data type: {type(data_raw)}, value: {data_raw}")
                        continue
                        
                elif stream_key == "tool_outputs":
                    # Tool outputs are dicts
                    if isinstance(data_raw, dict):
                        data = data_raw
                    else:
                        print(f"unexpected tool_outputs data type: {type(data_raw)}")
                        continue

                # Ensure data is a dictionary
                if not isinstance(data, dict):
                    print(f"data is not a dict after parsing: {type(data)}, value: {data}")
                    continue

                if stream_key == "input_mic":
                    # Handle input from client
                    event_type = data.get("type")
                    
                    if event_type == "input_audio_buffer.append":
                        # Send binary audio data                        
                        audio_data = data.get("audio")

                        # Process the audio with spectral gating if available
                        if AUDIO_PROCESSING_AVAILABLE:
                            try:
                                processed_audio = process_audio_with_spectral_gating(
                                    audio_data,
                                    sample_rate=TARGET_SAMPLE_RATE,
                                    stationary=False,
                                    prop_decrease=0.8,
                                )
                                audio_data = processed_audio
                            except Exception as e:
                                print(f"Error processing audio: {e}, sending original audio")

                        # Base64 encoded audio - decode first
                        audio_bytes = base64.b64decode(audio_data)

                        # Resample from 24kHz (client) to 16kHz (Gemini input)
                        resampled_audio = resample_audio(
                            audio_bytes,
                            from_rate=TARGET_SAMPLE_RATE,
                            to_rate=GEMINI_INPUT_SAMPLE_RATE
                        )
                        
                        # Encode back to base64 for Gemini
                        encoded_audio = base64.b64encode(resampled_audio).decode('utf-8')
                        
                        # Only send audio when model is not speaking
                        if not self._model_speaking:
                            await model_send({
                                "realtime_input": {
                                    "media_chunks": [{
                                        "data": encoded_audio,
                                        "mime_type": "audio/pcm",
                                    }]
                                }
                            })
                    else:
                        # Send other events as JSON
                        await model_send(data)
                        
                elif stream_key == "tool_outputs":
                    print("tool output", data)
                    # Gemini may handle tool outputs differently
                    # This is a placeholder - adjust based on Gemini's actual API
                    await model_send(data)
                    
                elif stream_key == "output_speaker":
                    # Handle responses from Gemini
                    try:
                        # Check for audio data in response
                        server_content = data.get("serverContent", {})
                        model_turn = server_content.get("modelTurn", {})
                        parts = model_turn.get("parts", [])
                        
                        if parts:
                            for part in parts:
                                inline_data = part.get("inlineData", {})
                                if inline_data and inline_data.get("data"):
                                    audio_data_b64 = inline_data["data"]
                                    
                                    if not self._model_speaking:
                                        self._model_speaking = True
                                        print("\nModel started speaking")
                                    
                                    # Decode base64 audio
                                    audio_bytes = base64.b64decode(audio_data_b64)
                                    
                                    '''
                                    # Gemini outputs at 24kHz, which matches our target
                                    # But we may need to process it
                                    if AUDIO_PROCESSING_AVAILABLE:
                                        try:
                                            # Process output audio
                                            processed_audio = process_audio_with_spectral_gating(
                                                audio_data_b64,
                                                sample_rate=GEMINI_OUTPUT_SAMPLE_RATE,
                                                stationary=True,
                                                prop_decrease=1.00,
                                            )
                                            audio_data_b64 = processed_audio
                                        except Exception as e:
                                            print(f"Error processing output audio: {e}")
                                    '''
                                    await send_output_chunk(json.dumps({
                                        "type": "response.audio.delta",
                                        "delta": audio_data_b64,
                                    }))
                        
                        # Check for turn complete
                        turn_complete = server_content.get("turnComplete", False)
                        if turn_complete:
                            print("\nEnd of turn")
                            # Wait a bit to ensure all audio is processed
                            await asyncio.sleep(0.5)
                            self._model_speaking = False
                            print("Ready for next input")
                            
                            # Save message exchange if available
                            if MESSAGE_TRACKING_AVAILABLE:
                                conversation_id = current_conversation_id.get()
                                if conversation_id and latest_user_input and latest_ai_response:
                                    try:
                                        create_message_exchange(
                                            conversation_id=conversation_id,
                                            user_input=latest_user_input,
                                            ai_response=latest_ai_response,
                                            input_tokens=None,  # Gemini may not provide token counts
                                            output_tokens=None,
                                            total_tokens=None,
                                        )
                                        # Reset for next exchange
                                        latest_user_input = None
                                        latest_ai_response = None
                                    except Exception as e:
                                        print(f"Error saving message exchange: {e}")
                        
                        # Check for text/transcript in response
                        # Gemini may provide transcripts in different parts
                        # This is a placeholder - adjust based on actual API response
                        text_content = model_turn.get("text", "")
                        if text_content:
                            latest_ai_response = text_content
                            await send_output_chunk(json.dumps({
                                "type": "response.audio_transcript.done",
                                "transcript": text_content,
                            }))
                    
                    except KeyError:
                        # Handle other response types
                        pass
                    
                    except Exception as e:
                        print(f"Error processing output: {e}")
                        import traceback
                        traceback.print_exc()


__all__ = ["GeminiVoiceReactAgent"]
