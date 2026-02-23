import asyncio
import json
import websockets

from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator, Any, Callable, Coroutine
from .utils import amerge

from langchain_core.tools import BaseTool
from langchain_core._api import beta
from langchain_core.utils import secret_from_env

from pydantic import BaseModel, Field, SecretStr, PrivateAttr

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
    from ..constants_openai import VOICE
    DEFAULT_VOICE = VOICE
except ImportError:
    DEFAULT_VOICE = "marin"  # Default fallback

# gpt-realtime model - updated from gpt-4o-realtime-preview-2024-10-01
DEFAULT_MODEL = "gpt-realtime"
DEFAULT_URL = "wss://api.openai.com/v1/realtime"

EVENTS_TO_IGNORE = {
    "response.function_call_arguments.delta",
    "rate_limits.updated",
    "response.created",
    "response.content_part.added",
    "response.content_part.done",
    "conversation.item.created",
    "response.audio.done",
    "session.created",
    "session.updated",
    "response.output_item.done",
}
# Note: response.done is NOT ignored - we need to handle it for message exchange tracking


@asynccontextmanager
async def connect(*, api_key: str, model: str, url: str) -> AsyncGenerator[
    tuple[
        Callable[[dict[str, Any] | str], Coroutine[Any, Any, None]],
        AsyncIterator[dict[str, Any]],
    ],
    None,
]:
    """
    async with connect(model="gpt-realtime") as websocket:
        await websocket.send("Hello, world!")
        async for message in websocket:
            print(message)
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",  # Required for gpt-realtime model
    }

    url = url or DEFAULT_URL
    url += f"?model={model}"

    websocket = await websockets.connect(url, additional_headers=headers)

    try:

        async def send_event(event: dict[str, Any] | str) -> None:
            formatted_event = json.dumps(event) if isinstance(event, dict) else event
            await websocket.send(formatted_event)

        async def event_stream() -> AsyncIterator[dict[str, Any]]:
            async for raw_event in websocket:
                yield json.loads(raw_event)

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
        # lock to avoid simultaneous tool calls racing and missing
        # _trigger_future being
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
            args = json.loads(tool_call["arguments"])
        except json.JSONDecodeError:
            raise ValueError(
                f"failed to parse arguments `{tool_call['arguments']}`. Must be valid JSON."
            )

        async def run_tool() -> dict:
            result = await tool.ainvoke(args)
            try:
                result_str = json.dumps(result)
            except TypeError:
                # not json serializable, use str
                result_str = str(result)
            return {
                "type": "conversation.item.create",
                "item": {
                    "id": tool_call["call_id"],
                    "call_id": tool_call["call_id"],
                    "type": "function_call_output",
                    "output": result_str,
                },
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
                            "type": "conversation.item.create",
                            "item": {
                                "id": tool_call["call_id"],
                                "call_id": tool_call["call_id"],
                                "type": "function_call_output",
                                "output": (f"Error: {str(e)}"),
                            },
                        }
                else:
                    yield task.result()


class OpenAIVoiceReactAgent(BaseModel):
    model: str
    api_key: SecretStr = Field(
        alias="openai_api_key",
        default_factory=secret_from_env("OPENAI_API_KEY", default=""),
    )
    instructions: str | None = None
    tools: list[BaseTool] | None = None
    url: str = Field(default=DEFAULT_URL)
    voice: str = Field(default=DEFAULT_VOICE)

    async def aconnect(
        self,
        input_stream: AsyncIterator[str],
        send_output_chunk: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Connect to the OpenAI API and send and receive messages.

        input_stream: AsyncIterator[str]
            Stream of input events to send to the model. Usually transports input_audio_buffer.append events from the microphone.
        output: Callable[[str], None]
            Callback to receive output events from the model. Usually sends response.audio.delta events to the speaker.

        """
        # formatted_tools: list[BaseTool] = [
        #     tool if isinstance(tool, BaseTool) else tool_converter.wr(tool)  # type: ignore
        #     for tool in self.tools or []
        # ]
        tools_by_name = {tool.name: tool for tool in self.tools}
        tool_executor = VoiceToolExecutor(tools_by_name=tools_by_name)
        
        # Track latest user input and AI response for message exchange
        latest_user_input: str | None = None
        latest_ai_response: str | None = None

        async with connect(
            model=self.model, api_key=self.api_key.get_secret_value(), url=self.url
        ) as (
            model_send,
            model_receive_stream,
        ):
            # Send tools and instructions with initial session update
            # Following OpenAI's recommended structure for gpt-realtime
            tool_defs = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {"type": "object", "properties": tool.args},
                }
                for tool in tools_by_name.values()
            ]
            await model_send(
                {
                    "type": "session.update",
                    "session": {
                        "modalities": ["audio", "text"],
                        "instructions": self.instructions,
                        "input_audio_transcription": {
                            "model": "whisper-1",
                        },
                        "voice": self.voice,
                        "tools": tool_defs,
                    },
                }
            )
            # Trigger initial response to start the conversation
            # Note: Usage data is included by default in response.done events for gpt-realtime
            await model_send({"type": "response.create", "response": {}})
            async for stream_key, data_raw in amerge(
                input_mic=input_stream,
                output_speaker=model_receive_stream,
                tool_outputs=tool_executor.output_iterator(),
            ):
                try:
                    data = (
                        json.loads(data_raw) if isinstance(data_raw, str) else data_raw
                    )
                except json.JSONDecodeError:
                    print("error decoding data:", data_raw)
                    continue

                if stream_key == "input_mic":
                    # Process audio with spectral gating if it's an audio event
                    if AUDIO_PROCESSING_AVAILABLE and should_process_audio_event(data):
                        try:
                            # Process the audio with spectral gating
                            processed_audio = process_audio_with_spectral_gating(
                                data["audio"],
                                sample_rate=24000,  # OpenAI Realtime API uses 24kHz
                                stationary=False,  # Non-stationary for varying noise
                                prop_decrease=0.8,  # Reduce 80% of noise
                            )
                            # Update the event with processed audio
                            data = {**data, "audio": processed_audio}
                        except Exception as e:
                            print(f"Error processing audio: {e}, sending original audio")
                    await model_send(data)
                elif stream_key == "tool_outputs":
                    print("tool output", data)
                    await model_send(data)
                    # Note: Usage data is included by default in response.done events for gpt-realtime
                    await model_send({"type": "response.create", "response": {}})
                elif stream_key == "output_speaker":

                    t = data["type"]
                    if t == "response.audio.delta":
                        await send_output_chunk(json.dumps(data))
                    elif t == "input_audio_buffer.speech_started":
                        print("nwew audio started")
                        await send_output_chunk(json.dumps(data))
                    elif t == "error":
                        print("error:", data)
                    elif t == "response.function_call_arguments.done":
                        print("tool call", data)
                        await tool_executor.add_tool_call(data)
                    elif t == "response.audio_transcript.done":
                        print("model:", data["transcript"])
                        # Store AI response transcript
                        latest_ai_response = data.get("transcript")
                        await send_output_chunk(json.dumps(data))
                    elif t == "conversation.item.input_audio_transcription.completed":
                        print("user:", data["transcript"])
                        # Store user input transcript
                        latest_user_input = data.get("transcript")
                        await send_output_chunk(json.dumps(data))
                    elif t == "response.done" or t == "response.complete":
                        # Save message exchange when response is complete
                        # Note: gpt-realtime uses "response.done" event with usage data in response.usage
                        if MESSAGE_TRACKING_AVAILABLE:
                            conversation_id = current_conversation_id.get()
                            if conversation_id:
                                # Extract usage data - structure: response.usage.{input_tokens, output_tokens, total_tokens}
                                response = data.get("response", {})
                                usage = response.get("usage", {})
                                
                                # Defensive extraction with fallbacks for gpt-realtime compatibility
                                # gpt-realtime provides aggregated tokens, but also supports granular audio/text breakdown
                                input_tokens = usage.get("input_tokens")
                                if input_tokens is None:
                                    # Fallback: calculate from audio/text tokens if aggregated not available
                                    input_tokens = usage.get("input_audio_tokens", 0) + usage.get("input_text_tokens", 0)
                                
                                output_tokens = usage.get("output_tokens")
                                if output_tokens is None:
                                    # Fallback: calculate from audio/text tokens if aggregated not available
                                    output_tokens = usage.get("output_audio_tokens", 0) + usage.get("output_text_tokens", 0)
                                
                                total_tokens = usage.get("total_tokens")
                                if total_tokens is None:
                                    # Fallback: calculate total if not provided
                                    total_tokens = input_tokens + output_tokens
                                try:
                                    create_message_exchange(
                                        conversation_id=conversation_id,
                                        user_input=latest_user_input,
                                        ai_response=latest_ai_response,
                                        input_tokens=input_tokens if input_tokens > 0 else None,
                                        output_tokens=output_tokens if output_tokens > 0 else None,
                                        total_tokens=total_tokens if total_tokens > 0 else None,
                                    )
                                except Exception as e:
                                    print(f"Error saving message exchange: {e}")
                        # Reset for next exchange
                        latest_user_input = None
                        latest_ai_response = None
                    elif t in EVENTS_TO_IGNORE:
                        pass
                    else:
                        pass
                        #print(t)


__all__ = ["OpenAIVoiceReactAgent"]
