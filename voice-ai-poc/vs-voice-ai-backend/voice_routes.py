from fastapi import APIRouter, WebSocket, Request, Depends

from openai_speech_to_speech import websocket_openai
from assemblyai_speech_to_speech import websocket_assemblyai
from gemini_speech_to_speech import websocket_gemini
from novasonic_speech_to_speech import websocket_novasonic
#from utils.utils import websocket_stream
from auth import verify_api_key, verify_websocket_api_key

router = APIRouter(
    prefix="",
)

@router.get("/", dependencies=[Depends(verify_api_key)])
def heart_beat(request: Request):
    return {"message": "Petvisor Voice API", "full_url": str(request.url)}


router.include_router(
    websocket_openai.router,
    prefix="/browser",
)

router.include_router(
    websocket_assemblyai.router,
    prefix="/browser",
)

router.include_router(
    websocket_gemini.router,
    prefix="/browser",
)

router.include_router(
    websocket_novasonic.router,
    prefix="/browser",
)

#@router.websocket("/ws-test")
#async def websocket_endpoint(websocket: WebSocket):
    # Verify API key before accepting connection
#    try:
#        await verify_websocket_api_key(websocket)
#    except ValueError:
#        # Connection already closed by verify_websocket_api_key
#        return
    
#    await websocket.accept()
#    async for message in websocket_stream(websocket):
#        await websocket.send_text(f"Received here in server and sending it back: {message}")
