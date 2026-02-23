import os
from typing import Any, Dict

from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from loguru import logger
from server_utils import (
    DialoutResponse,
    dialout_request_from_request,
    generate_twiml,
    make_twilio_call,
    parse_twiml_request,
)

# Keep values from current environment and use .env only as fallback.
load_dotenv(override=False)


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/dialout", response_model=DialoutResponse)
async def handle_dialout_request(request: Request) -> DialoutResponse:
    logger.info("Received outbound call request")

    dialout_request = await dialout_request_from_request(request)

    call_result = await make_twilio_call(dialout_request)

    return DialoutResponse(
        call_sid=call_result.call_sid,
        status="call_initiated",
        to_number=call_result.to_number,
    )


@app.post("/twiml")
async def get_twiml(request: Request) -> HTMLResponse:
    logger.info("Serving TwiML for outbound call")

    twiml_request = await parse_twiml_request(request)

    twiml_content = generate_twiml(twiml_request)

    return HTMLResponse(content=twiml_content, media_type="application/xml")

@app.post("/connect")
async def bot_connect(request: Request) -> Dict[Any, Any]:
    ws_url = "ws://localhost:7860/ws"
    return {"ws_url": ws_url}



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    from bot import twilio_bot, websocket_bot
    from pipecat.runner.types import WebSocketRunnerArguments

    await websocket.accept()
    logger.info("WebSocket connection accepted for outbound call")

    try:
        runner_args = WebSocketRunnerArguments(websocket=websocket)
        bot_type = os.getenv("BOT_TYPE", "websocket").strip().lower()
        if bot_type == "twilio":
            await twilio_bot(runner_args)
        elif bot_type == "websocket":
            await websocket_bot(runner_args)
        else:
            logger.error(
                f"Invalid BOT_TYPE '{bot_type}'. Expected one of: 'twilio', 'websocket'."
            )
            await websocket.close(code=1003, reason="Invalid BOT_TYPE")
            return
    except Exception as e:
        logger.error(f"Error in WebSocket endpoint: {e}")
        await websocket.close()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    logger.info(f"Starting Twilio outbound chatbot server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
