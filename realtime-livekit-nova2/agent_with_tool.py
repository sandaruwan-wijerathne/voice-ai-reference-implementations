import asyncio
import os
from livekit import agents
from livekit.agents import AgentSession, Agent, AutoSubscribe
from livekit.plugins.aws.experimental.realtime import RealtimeModel
from livekit.agents.llm.chat_context import ChatContext
from livekit.agents import function_tool, Agent, RunContext, JobExecutorType
from livekit.plugins import silero
import json
from typing import Any
from dotenv import load_dotenv
# Keep values from current environment and use .env only as fallback.
load_dotenv(override=False)

@function_tool()
async def lookup_weather(
    context: RunContext,
    location: str,
) -> dict[str, Any]:
    """Look up weather information for a given location.
    
    Args:
        location: The location to look up weather information for.
    """

    return {"weather": "sunny", "temperature_f": 70}

@function_tool()
async def get_user_profile(
    context: RunContext,
    username: str,
) -> dict[str, Any]:
    """Return dummy user profile data for a username.
    
    Args:
        username: The username to look up.
    """

    return {
        "username": username,
        "full_name": "John Doe",
        "email": "john.doe@example.com",
        "plan": "free",
    }

@function_tool()
async def get_user_preferences(
    context: RunContext,
    username: str,
) -> dict[str, Any]:
    """Return dummy user preferences for a username.
    
    Args:
        username: The username to look up.
    """
    await asyncio.sleep(20)
    return {"preferences": "I like to read books and watch movies."}

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    chat_ctx = ChatContext.empty()

    agent = Agent(
        instructions="You are a helpful voice AI assistant that can check weather and fetch user info by username.",
        chat_ctx=chat_ctx, 
        tools=[lookup_weather, get_user_profile, get_user_preferences]
    )
    realtime_model = RealtimeModel(voice="matthew")
    realtime_model.model_id = "amazon.nova-2-sonic-v1:0"
    session = AgentSession(
        vad=silero.VAD.load(),
        llm=realtime_model
        )
    
    await session.start(
        room=ctx.room,
        agent=agent,
    )

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            job_executor_type=JobExecutorType.THREAD,
            # Avoid clashes with other demos using 8081.
            port=int(os.getenv("LIVEKIT_AGENT_PORT", "0")),
        )
    )