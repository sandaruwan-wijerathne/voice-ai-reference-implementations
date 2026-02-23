from fastapi import HTTPException, Header, status
from starlette.websockets import WebSocket

from database import get_user_by_api_key

API_KEY_HEADER = "X-API-Key"


async def verify_api_key(api_key: str = Header(..., alias=API_KEY_HEADER)) -> dict:
    """
    Dependency to verify API key from request header.
    Raises 401 if key is invalid or missing.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required"
        )
    
    user = get_user_by_api_key(api_key)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return user


async def verify_websocket_api_key(websocket: WebSocket) -> dict:
    """
    Verify API key from WebSocket connection query parameters.
    Returns user dict if valid, closes connection with error if invalid.
    """
    api_key = websocket.query_params.get("api_key")
    
    if not api_key:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="API key is required")
        raise ValueError("API key is required")
    
    user = get_user_by_api_key(api_key)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid API key")
        raise ValueError("Invalid API key")
    
    return user

