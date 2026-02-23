from fastapi import APIRouter, Request, Depends
from starlette.websockets import WebSocket

from .constants_novasonic import SYSTEM_INSTRUCTION_VOICE
from .langchain_novasonic import NovaSonicVoiceReactAgent
from utils.tools import TOOLS_ARRAY, current_websocket, appointment_booked, current_conversation_id
from .websocket_utils import websocket_stream
from auth import verify_api_key, verify_websocket_api_key
from database import create_conversation, end_conversation
import os
import traceback

router = APIRouter(
    prefix="",
    tags=["browser_routes"],
)

@router.get("/", dependencies=[Depends(verify_api_key)])
def heart_beat(request: Request):
    return {"message": "Petvisor Voice API", "full_url": str(request.url)}

@router.websocket("/media-stream-novasonic")
async def websocket_endpoint(websocket: WebSocket):
    # Verify API key before accepting connection
    try:
        user = await verify_websocket_api_key(websocket)
    except ValueError:
        # Connection already closed by verify_websocket_api_key
        return
    
    await websocket.accept()

    # Create conversation record when conversation starts
    conversation_id = create_conversation(user["id"])
    
    # Store websocket in context variable so tools can access it
    current_websocket.set(websocket)
    
    # Store conversation_id in context variable so event handlers can access it
    current_conversation_id.set(conversation_id)
    
    # Initialize appointment booking tracking
    appointment_booked.set(False)

    browser_receive_stream = websocket_stream(websocket)

    # Get model ID and region from environment variables
    model_id = os.getenv('NOVA_SONIC_MODEL_ID', 'amazon.nova-2-sonic-v1:0')
    region = os.getenv('AWS_REGION', 'us-east-1')

    agent = NovaSonicVoiceReactAgent(
        model=model_id,
        region=region,
        tools=TOOLS_ARRAY,
        instructions=SYSTEM_INSTRUCTION_VOICE,
    )

    try:
        await agent.aconnect(browser_receive_stream, websocket.send_text)
    except Exception as e:
        print(f"Error in aconnect: {e}")
        traceback.print_exc()
    finally:
        # Update conversation record when conversation ends
        was_appointment_booked = appointment_booked.get(False)
        end_conversation(conversation_id, appointment_booked=was_appointment_booked)
        # Clear the websocket from context when connection ends
        current_websocket.set(None)
        current_conversation_id.set(None)
        appointment_booked.set(False)
