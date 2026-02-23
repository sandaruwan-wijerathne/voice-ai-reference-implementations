from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import logging

import voice_routes
from auth import verify_api_key
from database import DB_PATH

logger = logging.getLogger(__name__)

# Application version
APP_VERSION = "v.1.1"

router = APIRouter(
    prefix="",
)

@router.get("/health")
def health():
    """
    Health check endpoint with basic system verification.
    Returns 200 if healthy, 503 if unhealthy, 500 if health check fails.
    """
    try:
        health_status = {
            "status": "healthy",
            "checks": {
                "database": "unknown",
                "api": "ok"
            }
        }
        
        # Check if database file exists and is accessible
        try:
            if DB_PATH.exists():
                if DB_PATH.stat().st_size >= 0:
                    health_status["checks"]["database"] = "ok"
                else:
                    health_status["checks"]["database"] = "error"
                    health_status["status"] = "unhealthy"
            else:
                health_status["checks"]["database"] = "missing"
                logger.warning("Database file not found during health check")
        except Exception as e:
            logger.error(f"Health check database error: {e}")
            health_status["checks"]["database"] = "error"
            health_status["status"] = "unhealthy"
        
        # Return appropriate status code
        if health_status["status"] == "unhealthy":
            return JSONResponse(
                status_code=503,
                content=health_status
            )
        
        return health_status
        
    except Exception as e:
        # If health check itself fails, return 500
        logger.error(f"Health check endpoint error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Health check failed to execute",
                "error": str(e)
            }
        )

@router.get("/", dependencies=[Depends(verify_api_key)])
def heart_beat(request: Request):
    return {"message": "Petvisor Voice API", "full_url": str(request.url)}

@router.get("/version")
def get_version():
    """
    Returns the current version of the backend application.
    """
    return {"version": APP_VERSION}

router.include_router(
    voice_routes.router,
    prefix="/voice",
)