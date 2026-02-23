import asyncio
import json
import base64
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator, Any, Callable, Coroutine, Optional

import boto3

try:
    from aws_sdk_bedrock_runtime.client import BedrockRuntimeClient
    from aws_sdk_bedrock_runtime.models import (
        InvokeModelWithBidirectionalStreamInputChunk,
        BidirectionalInputPayloadPart,
        InvokeModelWithBidirectionalStreamOperationInput
    )
    from aws_sdk_bedrock_runtime.config import Config
    from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver
    AWS_SDK_AVAILABLE = True
except ImportError:
    AWS_SDK_AVAILABLE = False
    print("Warning: aws-sdk-bedrock-runtime not available. Install with: pip install aws-sdk-bedrock-runtime")

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
    from ..constants_novasonic import SYSTEM_INSTRUCTION_VOICE, VOICE_ID
    DEFAULT_INSTRUCTIONS = SYSTEM_INSTRUCTION_VOICE
    DEFAULT_VOICE_ID = VOICE_ID
except ImportError:
    DEFAULT_INSTRUCTIONS = "You are a helpful assistant."
    DEFAULT_VOICE_ID = "tiffany"

from ..constants_novasonic import (
    MODEL_ID,
    AWS_REGION,
    INPUT_SAMPLE_RATE,
    OUTPUT_SAMPLE_RATE,
    EVENT_SESSION_START,
    EVENT_CONTENT_START,
    EVENT_CONTENT_END,
    EVENT_TEXT_INPUT,
    EVENT_AUDIO_INPUT,
    EVENT_AUDIO_OUTPUT,
    EVENT_TEXT_OUTPUT,
    EVENT_TOOL_USE,
    EVENT_TOOL_RESULT,
    MEDIA_TYPE_AUDIO,
    MEDIA_TYPE_TEXT,
    ROLE_USER,
    ROLE_SYSTEM,
    ROLE_ASSISTANT,
)

EVENTS_TO_IGNORE = {
    "rate_limits.updated",
    "session.created",
    "session.updated",
}


def make_session_start_event():
    """Create a sessionStart event for Nova Sonic."""
    session_start = {
        "event": {
            EVENT_SESSION_START: {
                "inferenceConfiguration": { 
                    "maxTokens": 1024, 
                    "topP": 0.9, 
                    "temperature": 0.65},
                "turnDetectionConfiguration": {
                    "endpointingSensitivity": "MEDIUM" 
                }
            }
        }
    }
    return session_start

def convert_tools_to_nova_sonic_spec(tools: list[BaseTool] | None) -> list[dict]:
    """Convert LangChain tools to Nova Sonic 2 tool_spec format."""
    if not tools:
        return []
    
    tool_specs = []
    for tool in tools:
        # Get the input schema from the tool
        try:
            input_schema = tool.get_input_schema()
            schema_dict = input_schema.schema() if input_schema else {}
        except Exception:
            # Fallback: try args_schema
            if hasattr(tool, 'args_schema') and tool.args_schema:
                schema_dict = tool.args_schema.schema()
            else:
                schema_dict = {}
        
        # Extract properties and required fields
        properties = schema_dict.get("properties", {})
        required = schema_dict.get("required", [])
        
        # Build the tool spec in Nova Sonic 2 format
        tool_spec = {
            "toolSpec": {
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": {
                    "json": json.dumps({
                        "type": "object",
                        "properties": properties,
                        "required": required
                    })
                }
            }
        }
        tool_specs.append(tool_spec)
    
    return tool_specs


def make_prompt_start_event(prompt_name: str, voice_id: str = DEFAULT_VOICE_ID, tools: list[BaseTool] | None = None):
    """Create a promptStart event for Nova Sonic 2 with tool configuration."""
    prompt_start_data = {
        "promptName": prompt_name,
        "textOutputConfiguration": {
            "mediaType": "text/plain"
        },
        "audioOutputConfiguration": {
            "mediaType": "audio/lpcm",
            "sampleRateHertz": 24000,
            "sampleSizeBits": 16,
            "channelCount": 1,
            "voiceId": voice_id,
            "encoding": "base64",
            "audioType": "SPEECH"
        }
    }
    
    # Add tool configuration if tools are provided
    if tools:
        tool_specs = convert_tools_to_nova_sonic_spec(tools)
        if tool_specs:
            prompt_start_data["toolConfiguration"] = {
                "tools": tool_specs,
                "toolChoice": {"auto": {}}
            }
    
    prompt_start = {
        "event": {
            "promptStart": prompt_start_data
        }
    }
    return prompt_start


def make_text_content_start_event(prompt_name: str, content_name: str, role: str = "SYSTEM", interactive: bool = True):
    """Create a contentStart event for TEXT content in Nova Sonic."""
    return {
        "event": {
            EVENT_CONTENT_START: {
                "promptName": prompt_name,
                "contentName": content_name,
                "type": "TEXT",
                "interactive": interactive,
                "role": role,
                "textInputConfiguration": {
                    "mediaType": MEDIA_TYPE_TEXT
                }
            }
        }
    }


def make_audio_content_start_event(prompt_name: str, content_name: str, role: str = "SYSTEM", interactive: bool = True):
    """Create a contentStart event for AUDIO content in Nova Sonic."""
    return {
        "event": {
            EVENT_CONTENT_START: {
                "promptName": prompt_name,
                "contentName": content_name,
                "type": "AUDIO",
                "interactive": interactive,
                "role": role,
                "audioInputConfiguration": {
                    "mediaType": MEDIA_TYPE_AUDIO,
                    "sampleRateHertz": INPUT_SAMPLE_RATE,
                    "sampleSizeBits": 16,
                    "channelCount": 1,
                    "audioType": "SPEECH",
                    "encoding": "base64"
                }
            }
        }
    }


def make_tool_content_start_event(prompt_name: str, content_name: str, tool_use_id: str, role: str = "TOOL", interactive: bool = False):
    """Create a contentStart event for TOOL content in Nova Sonic."""
    return {
        "event": {
            EVENT_CONTENT_START: {
                "promptName": prompt_name,
                "contentName": content_name,
                "type": "TOOL",
                "interactive": interactive,
                "role": role,
                "toolResultInputConfiguration": {
                    "toolUseId": tool_use_id,
                    "type": "TEXT",
                    "textInputConfiguration": {
                        "mediaType": "text/plain"
                    }
                }
            }
        }
    }


def make_text_input_event(prompt_name: str, content_name: str, content: str):
    """Create a textInput event for Nova Sonic."""
    return {
        "event": {
            EVENT_TEXT_INPUT: {
                "promptName": prompt_name,
                "contentName": content_name,
                "content": content
            }
        }
    }


def make_content_end_event(prompt_name: str, content_name: str):
    """Create a contentEnd event for Nova Sonic."""
    return {
        "event": {
            EVENT_CONTENT_END: {
                "promptName": prompt_name,
                "contentName": content_name
            }
        }
    }


def make_tool_result_event(prompt_name: str, content_name: str, tool_use_id: str, content: str):
    """Create a toolResult event for Nova Sonic 2."""
    return {
        "event": {
            EVENT_TOOL_RESULT: {
                "promptName": prompt_name,
                "contentName": content_name,
                "toolUseId": tool_use_id,
                "content": content
            }
        }
    }


def make_audio_input_event(prompt_name: str, content_name: str, audio_chunk_base64: str):
    """Create an audioInput event for Nova Sonic."""
    return {
        "event": {
            EVENT_AUDIO_INPUT: {
                "promptName": prompt_name,
                "contentName": content_name,
                "content": audio_chunk_base64
            }
        }
    }


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

        # try to parse args - Nova Sonic 2 provides arguments as a dict or JSON string
        try:
            args = tool_call.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)
            elif not isinstance(args, dict):
                args = {}
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
            
            # Return ToolResult event for Nova Sonic 2
            tool_use_id = tool_call.get("toolUseId") or tool_call.get("id", "")
            return make_tool_result_event(tool_call["promptName"], tool_call["contentName"], tool_use_id, result_str)

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
                        # Return error as ToolResult event
                        tool_use_id = tool_call.get("toolUseId") or tool_call.get("id", "")
                        yield make_tool_result_event(tool_use_id, f"Error: {str(e)}")
                else:
                    yield task.result()


class NovaSonicStream:
    """
    Manages bidirectional streaming communication with Nova Sonic via AWS Bedrock Runtime.
    
    Uses the AWS SDK for Python v2 (aws-sdk-bedrock-runtime) for true bidirectional streaming.
    This allows sending events and receiving responses simultaneously on a single persistent connection.
    
    Based on the AWS sample implementation:
    https://github.com/aws-samples/amazon-nova-samples/blob/main/speech-to-speech/sample-codes/console-python/nova_sonic_simple.py
    """
    
    def __init__(self, model_id: str, region: str, instructions: str = None, prompt_name: str = None, content_name:str=None, audio_content_name: str = None, tools: list[BaseTool] | None = None):
        if not AWS_SDK_AVAILABLE:
            raise ImportError(
                "aws-sdk-bedrock-runtime is required. Install with: pip install aws-sdk-bedrock-runtime"
            )
        
        self.model_id = model_id
        self.region = region
        self.instructions = instructions
        self.tools = tools
        self.client = None
        self.stream = None
        self.prompt_name = prompt_name if prompt_name else str(uuid.uuid4())
        self.content_name = content_name if content_name else str(uuid.uuid4())
        self.audio_content_name = audio_content_name if audio_content_name else str(uuid.uuid4())
        self.input_queue = asyncio.Queue()
        self.output_queue = asyncio.Queue()
        self.streaming_active = True
        self._output_task = None
        self._input_task = None
        self._initialized = False
        
    def _initialize_client(self):
        """Initialize the Bedrock Runtime client."""
        if self.client is None:
            config = Config(
                endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
                region=self.region,
                aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
            )
            self.client = BedrockRuntimeClient(config=config)
    
    async def initialize(self):
        """Initialize the bidirectional stream with session start and system instructions."""
        if self._initialized:
            return
        
        # Initialize the client
        self._initialize_client()
        print(f"Initializing stream for model: {self.model_id}")

        # Initialize the bidirectional stream
        self.stream = await self.client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(model_id=self.model_id)
        )
        
        # Start processing responses in the background
        self._output_task = asyncio.create_task(self._process_responses())
        
        # Send session start event
        session_start_event = make_session_start_event()
        await self._send_event_internal(session_start_event)
        
        # Send prompt start event with tool configuration
        prompt_start_event = make_prompt_start_event(self.prompt_name, VOICE_ID, self.tools)
        #print(f"Prompt start event: {prompt_start_event}")
        await self._send_event_internal(prompt_start_event)

        # Send system prompt
        text_content_start = make_text_content_start_event(self.prompt_name, self.content_name, "SYSTEM", False)
        await self._send_event_internal(text_content_start)

        system_prompt = self.instructions
        text_input = make_text_input_event(self.prompt_name, self.content_name, system_prompt)
        await self._send_event_internal(text_input)

        text_content_end = make_content_end_event(self.prompt_name, self.content_name)
        await self._send_event_internal(text_content_end)

        # Prompt model by sending an initial text input event
        initial_text_content_name = str(uuid.uuid4())
        text_content_start = make_text_content_start_event(self.prompt_name, initial_text_content_name, "USER", True)
        await self._send_event_internal(text_content_start)        
        initial_text_input = make_text_input_event(self.prompt_name, initial_text_content_name, "Hello!")
        await self._send_event_internal(initial_text_input)
        text_content_end = make_content_end_event(self.prompt_name, initial_text_content_name)
        await self._send_event_internal(text_content_end)

        # Start audio input stream
        audio_content_start = make_audio_content_start_event(self.prompt_name, self.audio_content_name, ROLE_USER, interactive=True)
        await self._send_event_internal(audio_content_start)

        self._initialized = True
        
        # Start processing input queue to send events
        self._input_task = asyncio.create_task(self._process_input_queue())

    
    async def _send_event_internal(self, event: dict[str, Any]) -> None:
        """Internal method to send an event to the bidirectional stream."""
        if not self.stream:
            raise RuntimeError("Stream not initialized. Call initialize() first.")
        
        event_json = json.dumps(event)
        #print(f"Sending event: {event_json}")
        chunk = InvokeModelWithBidirectionalStreamInputChunk(
            value=BidirectionalInputPayloadPart(bytes_=event_json.encode('utf-8'))
        )
        await self.stream.input_stream.send(chunk)
    
    async def send_event(self, event: dict[str, Any] | str) -> None:
        """Send an event to the bidirectional stream."""
        if isinstance(event, str):
            event = json.loads(event)
        
        if not self._initialized:
            # Queue the event if not initialized yet
            await self.input_queue.put(event)
        else:
            # Send directly if initialized
            try:
                await self._send_event_internal(event)
            except Exception as e:
                print(f"Error sending event to Bedrock: {e}")
                await self.output_queue.put({
                    "error": str(e)
                })
    
    async def _process_responses(self):
        """Process responses from the bidirectional stream."""
        try:
            while self.streaming_active:
                try:
                    output = await self.stream.await_output()
                    result = await output[1].receive()
                    #print(f"Result: {result}")
                    if result.value and result.value.bytes_:
                        response_data = result.value.bytes_.decode('utf-8')
                        json_data = json.loads(response_data)
                        
                        # Handle Nova Sonic event-based responses
                        if 'event' in json_data:
                            event = json_data['event']
                            
                            # Handle content start event
                            if 'contentStart' in event:
                                # Content start - we can track role if needed
                                pass
                            
                            # Handle text output event
                            elif 'textOutput' in event:
                                text_output = event['textOutput']
                                await self.output_queue.put({
                                    "event": {
                                        EVENT_TEXT_OUTPUT: {
                                            "content": text_output.get('content', '')
                                        }
                                    }
                                })
                            
                            # Handle audio output event
                            elif 'audioOutput' in event:
                                audio_output = event['audioOutput']
                                await self.output_queue.put({
                                    "event": {
                                        EVENT_AUDIO_OUTPUT: {
                                            "content": audio_output.get('content', '')
                                        }
                                    }
                                })
                            
                            # Handle toolUse event for Nova Sonic 2
                            elif EVENT_TOOL_USE in event:
                                print("\n")
                                print(f"Tool use event: {event[EVENT_TOOL_USE]}")
                                print("\n")
                                tool_use = event[EVENT_TOOL_USE]
                                await self.output_queue.put({
                                    "event": {
                                        EVENT_TOOL_USE: tool_use
                                    }
                                })
                            
                            # Handle other events - pass through
                            else:
                                await self.output_queue.put(json_data)
                        else:
                            # Unknown format, pass through
                            await self.output_queue.put(json_data)
                            
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Error processing response: {e}")
                    if self.streaming_active:
                        await self.output_queue.put({
                            "error": str(e)
                        })
                    raise e
                    
        except Exception as e:
            print(f"Error in response processing: {e}")
            import traceback
            traceback.print_exc()
            if self.streaming_active:
                await self.output_queue.put({
                    "error": str(e)
                })
    
    async def _process_input_queue(self):
        """Process queued input events and send them to Bedrock."""
        while self.streaming_active:
            try:
                event = await asyncio.wait_for(self.input_queue.get(), timeout=0.1)
                await self._send_event_internal(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing input event: {e}")
                if self.streaming_active:
                    break
    
    async def get_output(self) -> AsyncIterator[dict[str, Any]]:
        """Get output events from the stream."""
        while self.streaming_active or not self.output_queue.empty():
            try:
                event = await asyncio.wait_for(self.output_queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                if not self.streaming_active:
                    break
                continue
    
    async def close(self):
        """Close the stream and end the session."""
        self.streaming_active = False
        
        # Send session end events if stream is active
        if self.stream and self._initialized:
            try:
                # Send prompt end
                prompt_end = {
                    "event": {
                        "promptEnd": {
                            "promptName": self.prompt_name
                        }
                    }
                }
                await self._send_event_internal(prompt_end)
                
                # Send session end
                session_end = {
                    "event": {
                        "sessionEnd": {}
                    }
                }
                await self._send_event_internal(session_end)
                
                # Close the input stream
                await self.stream.input_stream.close()
            except Exception as e:
                print(f"Error closing stream: {e}")
        
        # Cancel tasks
        if self._output_task:
            self._output_task.cancel()
            try:
                await self._output_task
            except asyncio.CancelledError:
                pass
        
        if self._input_task:
            self._input_task.cancel()
            try:
                await self._input_task
            except asyncio.CancelledError:
                pass


@asynccontextmanager
async def connect(*, model_id: str, region: str, instructions: str = None, prompt_name: str = None, content_name:str=None,audio_content_name: str = None, tools: list[BaseTool] | None = None) -> AsyncGenerator[
    tuple[
        Callable[[dict[str, Any] | str], Coroutine[Any, Any, None]],
        AsyncIterator[dict[str, Any]],
    ],
    None,
]:
    """
    Connect to AWS Bedrock Runtime for Nova Sonic bidirectional streaming.
    
    Uses the AWS SDK for Python v2 (aws-sdk-bedrock-runtime) for true bidirectional streaming.
    This allows sending events and receiving responses simultaneously on a single persistent connection.
    
    Based on the AWS sample implementation:
    https://github.com/aws-samples/amazon-nova-samples/blob/main/speech-to-speech/sample-codes/console-python/nova_sonic_simple.py
    
    Args:
        model_id: Nova Sonic model ID (e.g., "amazon.nova-sonic-v1:0" or "amazon.nova-2-sonic-v1:0")
        region: AWS region
        instructions: System instructions for the agent
    """
    stream = NovaSonicStream(model_id, region, instructions, prompt_name, content_name, audio_content_name, tools)
    await stream.initialize()
    
    async def send_event(event: dict[str, Any] | str) -> None:
        """Send an event to the bidirectional stream."""
        await stream.send_event(event)

    async def event_stream() -> AsyncIterator[dict[str, Any]]:
        """Stream events from output queue."""
        async for event in stream.get_output():
            #print(f"Sending event: {event}")
            yield event

    try:
        yield send_event, event_stream()
    finally:
        await stream.close()


class NovaSonicVoiceReactAgent(BaseModel):
    model: str = Field(default=MODEL_ID)
    region: str = Field(default=AWS_REGION)
    instructions: str | None = Field(default=DEFAULT_INSTRUCTIONS)
    tools: list[BaseTool] | None = None

    async def aconnect(
        self,
        input_stream: AsyncIterator[str],
        send_output_chunk: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Connect to Nova Sonic and send and receive messages.

        input_stream: AsyncIterator[str]
            Stream of input events to send to the model. Usually transports audio events from the microphone.
        send_output_chunk: Callable[[str], None]
            Callback to receive output events from the model. Usually sends audio events to the speaker.
        """
        tools_by_name = {tool.name: tool for tool in (self.tools or [])}
        tool_executor = VoiceToolExecutor(tools_by_name=tools_by_name)
        
        # Track latest user input and AI response for message exchange
        latest_user_input: str | None = None
        latest_ai_response: str | None = None

        prompt_name = str(uuid.uuid4())
        content_name = str(uuid.uuid4())
        audio_content_name = str(uuid.uuid4())

        async with connect(
            model_id=self.model,
            region=self.region,
            instructions=self.instructions,
            prompt_name=prompt_name,
            content_name=content_name,
            audio_content_name=audio_content_name,
            tools=self.tools
        ) as (
            model_send,
            model_receive_stream,
        ):
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
                    # Process audio input from client
                    # Expected format: JSON with audio data or raw audio event
                    if isinstance(data, dict) and "audio" in data:
                        # Audio data in base64
                        audio_base64 = data["audio"]
                        event = make_audio_input_event(prompt_name, audio_content_name, audio_base64)
                        await model_send(event)
                    elif isinstance(data, dict) and "type" in data:
                        # Forward other event types
                        await model_send(data)
                        
                elif stream_key == "tool_outputs":
                    tool_content_name = str(uuid.uuid4())
                    tool_use_id = data["event"]['toolResult']["toolUseId"]
                    await model_send(make_tool_content_start_event(prompt_name, tool_content_name, tool_use_id, "TOOL", False))
                    data["event"]['toolResult']["contentName"] = tool_content_name
                    await model_send(data)
                    await model_send(make_content_end_event(prompt_name, tool_content_name))
                    
                elif stream_key == "output_speaker":
                    # Process output from Nova Sonic
                    if "event" in data:
                        event = data["event"]
                        
                        if EVENT_AUDIO_OUTPUT in event:
                            # Audio output from Nova Sonic
                            audio_base64 = event[EVENT_AUDIO_OUTPUT]['content']
                            await send_output_chunk(json.dumps({
                                "type": "response.audio.delta",
                                "delta": audio_base64
                            }))

                        elif EVENT_TEXT_OUTPUT in event:
                            # Text output/transcript from Nova Sonic
                            text_output = event[EVENT_TEXT_OUTPUT]
                            transcript = text_output.get("content", "")
                            latest_ai_response = transcript
                            print("model:", transcript)
                            await send_output_chunk(json.dumps({
                                "type": "transcript",
                                "transcript": transcript
                            }))
                        
                        elif EVENT_TOOL_USE in event:
                            # Handle toolUse event from Nova Sonic 2
                            tool_use = event[EVENT_TOOL_USE]
                            #print(f"Tool use received: {tool_use}")
                            # Extract tool call information
                            tool_call = {
                                "promptName": tool_use.get("promptName", ""),
                                "contentName": tool_use.get("contentId", ""),
                                "name": tool_use.get("toolName", ""),
                                "arguments": tool_use.get("content", {}),
                                "toolUseId": tool_use.get("toolUseId", "")
                            }
                            # Add tool call to executor
                            await tool_executor.add_tool_call(tool_call)
                        
                        elif "error" in event:
                            print("error:", event["error"])
                            await send_output_chunk(json.dumps({
                                "type": "error",
                                "error": str(event["error"])
                            }))
                    elif "error" in data:
                        print("error:", data["error"])
                        await send_output_chunk(json.dumps({
                            "type": "error",
                            "error": str(data["error"])
                        }))
                else:
                    print("unknown event:", data)


__all__ = ["NovaSonicVoiceReactAgent"]
