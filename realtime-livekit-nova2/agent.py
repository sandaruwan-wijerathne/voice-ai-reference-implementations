from livekit import agents
from livekit.agents import AgentSession, Agent, AutoSubscribe
from livekit.plugins.aws.experimental.realtime import RealtimeModel
from dotenv import load_dotenv
import os
# Keep values from current environment and use .env only as fallback.
load_dotenv(override=False)

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    system_prompt = os.getenv("VOICE_SYSTEM_PROMPT")
    if not system_prompt:
        raise RuntimeError(
            "VOICE_SYSTEM_PROMPT is required. Set it via exported env vars or integration_demos/.env.shared."
        )

    agent = Agent(instructions=system_prompt)
    realtime_model = RealtimeModel()
    realtime_model.model_id = "amazon.nova-2-sonic-v1:0"
    session = AgentSession(llm=realtime_model)
    
    await session.start(
        room=ctx.room,
        agent=agent,
    )

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            # Avoid clashes with other demos using 8081.
            port=int(os.getenv("LIVEKIT_AGENT_PORT", "0")),
        )
    )