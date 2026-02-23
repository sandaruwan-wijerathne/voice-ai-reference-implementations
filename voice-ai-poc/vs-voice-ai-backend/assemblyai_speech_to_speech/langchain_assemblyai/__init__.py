import asyncio
import json
import base64
import websockets
import httpx
import numpy as np
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator, Any, Callable, Coroutine, Optional

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
        reduce_gain_pcm,
    )
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    print("Warning: Audio processing utilities not available. Install noisereduce and numpy.")

# Import voice configuration
try:
    from ..constants_assemblyai import VOICE
    DEFAULT_VOICE = VOICE
except ImportError:
    DEFAULT_VOICE = "luna"  # Default fallback

# AssemblyAI WebSocket URL
DEFAULT_URL = "wss://aaigentsv1.up.railway.app/ws"
# AssemblyAI REST API URL
REST_API_URL = "https://aaigentsv1.up.railway.app"

EVENTS_TO_IGNORE = {
    "rate_limits.updated",
    "session.created",
    "session.updated",
}

# Audio configuration
ASSEMBLYAI_SAMPLE_RATE = 16000  # Default AssemblyAI audio sample rate
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
async def connect(*, api_key: str, agent_id: str, url: str) -> AsyncGenerator[
    tuple[
        Callable[[dict[str, Any] | str | bytes], Coroutine[Any, Any, None]],
        AsyncIterator[dict[str, Any]],
    ],
    None,
]:
    """
    Connect to AssemblyAI's WebSocket API for voice agents.
    
    Args:
        api_key: AssemblyAI API key
        agent_id: The agent ID to connect to
        url: WebSocket URL (defaults to AssemblyAI's realtime endpoint)
    """
    # AssemblyAI WebSocket connection with agent_id as query parameter
    # Note: According to docs, WebSocket doesn't require auth, but custom endpoints might
    ws_url = f"{url}/{agent_id}"
    
    # Only add auth header if api_key is provided (for custom endpoints)
    # According to docs: WebSocket doesn't require auth, but custom endpoints might
    headers = {}
    if api_key:
        headers["Authorization"] = api_key
    
    websocket = await websockets.connect(
        ws_url
    )

    try:
        async def send_event(event: dict[str, Any] | str | bytes) -> None:
            if isinstance(event, bytes):
                # Binary audio data
                await websocket.send(event)
            elif isinstance(event, dict):
                # JSON event
                formatted_event = json.dumps(event)
                await websocket.send(formatted_event)
            else:
                # String event
                await websocket.send(event)

        async def event_stream() -> AsyncIterator[dict[str, Any]]:
            async for message in websocket:
                #print("EVENT: message", message)
                if isinstance(message, bytes):
                    #print("EVENT: Audio data received")
                    # Binary audio data - yield as raw bytes wrapped in dict for processing
                    # According to docs: Raw PCM audio as binary WebSocket frame
                    yield {
                        "type": "audio",
                        "data": message  # Keep as bytes, not base64
                    }
                else:
                    #print("EVENT: JSON data received")
                    print("EVENT: message", message)
                    # JSON event
                    try:
                        yield json.loads(message)
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


class AssemblyAIVoiceReactAgent(BaseModel):
    agent_id: Optional[str] = None
    agent_name: str = Field(default="Petvisor_Voice_Agent")
    api_key: SecretStr = Field(
        alias="assemblyai_api_key",
        default_factory=secret_from_env("ASSEMBLYAI_API_KEY", default=""),
    )
    instructions: str | None = None
    tools: list[BaseTool] | None = None
    url: str = Field(default=DEFAULT_URL)
    voice: str = Field(default=DEFAULT_VOICE)
    llm: str = Field(default="gpt-4o-mini")

    async def _list_agents(self) -> list[dict]:
        """List all agents for the authenticated user."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{REST_API_URL}/agents",
                headers={
                    "Authorization": self.api_key.get_secret_value(),
                },
            )
            response.raise_for_status()
            data = response.json()
            # Handle both direct array response and nested "agents" field
            if isinstance(data, list):
                return data
            return data.get("agents", [])

    async def _get_agent_by_name(self, name: str) -> Optional[dict]:
        """Get an agent by name from the list of agents."""
        agents = await self._list_agents()
        for agent in agents:
            if agent == name:
                return agent
        return None

    async def _create_or_update_agent(self) -> dict:
        """Create a new agent with the configured instructions and tools."""
        # Convert tools to AssemblyAI format
        tool_defs = []
        if self.tools:
            for tool in self.tools:
                # Get tool properties - use tool.args if available (like OpenAI implementation)
                # Otherwise try to get from args_schema
                if hasattr(tool, 'args') and tool.args:
                    properties = tool.args
                elif hasattr(tool, 'args_schema') and tool.args_schema:
                    tool_schema = tool.args_schema.schema()
                    properties = tool_schema.get("properties", {})
                else:
                    # Fallback: try to get input schema
                    try:
                        input_schema = tool.get_input_schema()
                        properties = input_schema.schema().get("properties", {}) if input_schema else {}
                    except:
                        properties = {}
                
                # Get required fields
                required = []
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    tool_schema = tool.args_schema.schema()
                    required = tool_schema.get("required", [])
                else:
                    try:
                        input_schema = tool.get_input_schema()
                        if input_schema:
                            required = input_schema.schema().get("required", [])
                    except:
                        pass
                
                # Convert to AssemblyAI tool format
                # According to docs: Tool Definition Schema requires:
                # - type: "function"
                # - name: string
                # - description: string
                # - parameters: object with type, properties, and required fields
                tool_def = {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required if required else [],  # Ensure required is always a list
                    },
                }
                tool_defs.append(tool_def)

        # According to AssemblyAI docs, agent creation payload should include:
        # - name (required): Agent name/identifier
        # - instructions (optional): System instructions for the agent
        # - voice (optional): Voice to use for TTS
        # - llm (optional): LLM model to use
        # - language (optional): Language code (default: "en")
        # - tools (optional): Array of tool definitions
        # Additional optional fields may include:
        # - audio_in_sample_rate, audio_out_sample_rate, temperature, etc.
        agent_config = {
            "agent_name": "Petvisor_Voice_Agent",
            "instructions": self.instructions,
            "voice": self.voice,
            "language": "en",
            "audio_in_sample_rate": 24000,
            "audio_out_sample_rate": 24000,
            "tools": tool_defs,
        }
        
        # Add tools if provided
        #if tool_defs:
        #    agent_config["tools"] = tool_defs

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{REST_API_URL}/agents",
                headers={
                    "Authorization": self.api_key.get_secret_value(),
                    "Content-Type": "application/json",
                },
                json=agent_config,
            )
            #print("agent_config", agent_config)
            #print("response", response.json())
            response.raise_for_status()
            return response.json()

    async def _ensure_agent(self) -> str:
        """Ensure an agent exists, creating one if necessary. Update the configuration. Returns agent_id."""
        # If agent_id is provided, use it
        if self.agent_id:
            return self.agent_id
        
        # Check if agent exists by name
        agent_exists = False
        existing_agent = await self._get_agent_by_name(self.agent_name)
        if existing_agent:
            agent_id = existing_agent
            if agent_id:
                agent_exists = True
        
        # Create new agent/update existing agent
        if not agent_exists:
            print(f"Creating new agent: {self.agent_name}")
            new_agent = await self._create_or_update_agent()
            agent_id = new_agent.get("agent_id") or new_agent.get("id") or new_agent.get("agent_name")
        else:
            print(f"Updating existing agent: {self.agent_name}")
            new_agent = await self._create_or_update_agent()
            agent_id = new_agent.get("agent_id") or new_agent.get("id") or new_agent.get("agent_name")
        
        if not agent_id:
            raise ValueError(f"Failed to create agent: no agent_id in response. Response: {new_agent}")
        if not agent_exists:
            print(f"Created agent: {self.agent_name} (ID: {agent_id})")
        else:
            print(f"Updated agent: {self.agent_name} (ID: {agent_id})")
        return agent_id

    async def aconnect(
        self,
        input_stream: AsyncIterator[str],
        send_output_chunk: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Connect to the AssemblyAI API and send and receive messages.

        input_stream: AsyncIterator[str]
            Stream of input events to send to the model. Usually transports audio data from the microphone.
        send_output_chunk: Callable[[str], None]
            Callback to receive output events from the model. Usually sends audio events to the speaker.
        """
        # Ensure agent exists (create if needed)
        agent_id = await self._ensure_agent()
        
        tools_by_name = {tool.name: tool for tool in (self.tools or [])}
        tool_executor = VoiceToolExecutor(tools_by_name=tools_by_name)
        
        # Track latest user input and AI response for message exchange
        latest_user_input: str | None = None
        latest_ai_response: str | None = None

        async with connect(
            api_key=self.api_key.get_secret_value(),
            agent_id=agent_id,
            url=self.url
        ) as (
            model_send,
            model_receive_stream,
        ):
            # Note: AssemblyAI agents are configured via REST API, not WebSocket
            # session.created event will come through the stream naturally
            
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
                    #print("EVENT: Output speaker")
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

                        # Process the audio with spectral gating
                        processed_audio = process_audio_with_spectral_gating(
                            audio_data,
                            sample_rate=24000,  # OpenAI Realtime API uses 24kHz
                            stationary=False,  # Non-stationary for varying noise
                            prop_decrease=0.8,  # Reduce 80% of noise
                        )

                        # Base64 encoded audio - decode first
                        audio_bytes = base64.b64decode(processed_audio)
                        
                        await model_send(audio_bytes)

                    else:
                        # Send other events as JSON
                        await model_send(data)
                        
                elif stream_key == "tool_outputs":
                    print("tool output", data)
                    await model_send(data)
                    
                elif stream_key == "output_speaker":
                    event_type = data.get("type")
                    
                    # Handle session.created event (sent when WebSocket connection is established)
                    if event_type == "session.created":
                        print("****Session created")
                        await send_output_chunk(json.dumps(data))
                        continue
                    
                    elif event_type == "audio":
                        # Binary audio response from server
                        audio_data = data.get("data")

                        # Base64 encode for JSON transport
                        encoded_audio = base64.b64encode(audio_data).decode('utf-8')
                        
                        await send_output_chunk(json.dumps({
                            "type": "response.audio.delta",
                            "delta": encoded_audio,
                        }))

                    elif event_type == "conversation.item.done":
                        print("conversation.item.done", data)
                        # Conversation item completed
                        item = data.get("item", {})
                        item_type = item.get("type")
                        
                        if item_type == "message":
                            # Extract message content
                            content = item.get("content", "")
                            role = item.get("role", "assistant")
                            
                            if role == "user":
                                latest_user_input = content
                            elif role == "assistant":
                                latest_ai_response = content
                            
                            # Forward the event
                            await send_output_chunk(json.dumps(data))
                            
                            # Save message exchange when conversation item is done
                            if MESSAGE_TRACKING_AVAILABLE:
                                conversation_id = current_conversation_id.get()
                                if conversation_id:
                                    # Try to save message exchange if we have both
                                    if latest_user_input and latest_ai_response:
                                        try:
                                            create_message_exchange(
                                                conversation_id=conversation_id,
                                                user_input=latest_user_input,
                                                ai_response=latest_ai_response,
                                                input_tokens=None,  # AssemblyAI doesn't provide token counts in the same way
                                                output_tokens=None,
                                                total_tokens=None,
                                            )
                                            # Reset for next exchange
                                            latest_user_input = None
                                            latest_ai_response = None
                                        except Exception as e:
                                            print(f"Error saving message exchange: {e}")
                        elif item_type == "function_call":
                            # Tool call completed
                            await send_output_chunk(json.dumps(data))
                        else:
                            await send_output_chunk(json.dumps(data))
                            
                    elif event_type == "conversation.item.interim":
                        # Interim transcription
                        item = data.get("item", {})
                        if item.get("type") == "message":
                            transcript = item.get("content", "")
                            await send_output_chunk(json.dumps({
                                "type": "conversation.item.interim",
                                "transcript": transcript
                            }))
                            
                    elif event_type == "tool.call":
                        # Tool call from agent
                        # According to docs: Server sends tool.call event with name and arguments
                        print("tool call", data)
                        tool_call_data = {
                            "name": data.get("name"),
                            "arguments": data.get("arguments", {}),
                            "tool_call_id": data.get("tool_call_id", data.get("id")),
                        }
                        await tool_executor.add_tool_call(tool_call_data)
                        
                    elif event_type == "error":
                        print("error:", data)
                        await send_output_chunk(json.dumps(data))
                        
                    elif event_type in EVENTS_TO_IGNORE:
                        pass
                    else:
                        # Forward other events
                        await send_output_chunk(json.dumps(data))
                

__all__ = ["AssemblyAIVoiceReactAgent"]
