from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger, setup_logging
from app.db.indexes import create_indexes
from app.db.mongodb import mongo_manager
from app.schemas.common import ErrorDetails, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    setup_logging(settings.LOG_LEVEL)
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' mode.")
    settings.validate_production_readiness()

    try:
        await mongo_manager.connect()
        logger.info("Connected to MongoDB successfully.")
        await create_indexes()
    except Exception as exc:
        logger.error(f"Error during MongoDB startup initialization: {exc}")

    yield

    # Shutdown sequence
    logger.info("Initiating graceful shutdown...")
    await mongo_manager.close()
    logger.info("Shutdown completed.")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Production-ready customer authentication and profile management module for Kirna Kart.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Global Exception Handlers for Envelope Standardization
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    error_payload = ErrorResponse(
        success=False,
        message=exc.message,
        error=ErrorDetails(code=exc.code, details=exc.details),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload.model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    clean_details = []
    for err in exc.errors():
        clean_details.append({
            "loc": [str(loc_item) for loc_item in err.get("loc", [])],
            "msg": err.get("msg"),
            "type": err.get("type"),
        })

    error_payload = ErrorResponse(
        success=False,
        message="Request validation failed. Please check your submitted data.",
        error=ErrorDetails(code="VALIDATION_ERROR", details=clean_details),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload.model_dump(),
    )


@app.exception_handler(PyMongoError)
async def pymongo_exception_handler(request: Request, exc: PyMongoError) -> JSONResponse:
    logger.error(f"Database operation failed: {exc}", exc_info=True)
    error_payload = ErrorResponse(
        success=False,
        message="Database service is temporarily unavailable. If connecting to MongoDB Atlas, ensure '0.0.0.0/0' is added to Atlas Network Access IP whitelist.",
        error=ErrorDetails(code="DATABASE_UNAVAILABLE", details=[str(exc)]),
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=error_payload.model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    error_payload = ErrorResponse(
        success=False,
        message="An unexpected internal server error occurred.",
        error=ErrorDetails(code="INTERNAL_SERVER_ERROR", details=[]),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload.model_dump(),
    )


# Root Route
@app.api_route(
    "/",
    methods=["GET", "HEAD"],
    tags=["System"],
    summary="Root Service Status",
    description="Welcome endpoint providing service metadata and API documentation links.",
    status_code=status.HTTP_200_OK,
)
async def root() -> Dict[str, Any]:
    return {
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "status": "online",
        "version": "1.0.0",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": "/openapi.json",
        },
        "health": {
            "liveness": "/health",
            "readiness": "/ready",
        },
    }


# Lightweight Liveness Check
@app.api_route(
    "/health",
    methods=["GET", "HEAD"],
    tags=["System"],
    summary="Lightweight Liveness Check",
    description="Returns lightweight liveness status without exposing internal details.",
    status_code=status.HTTP_200_OK,
)
async def liveness_check() -> Dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME}


# Dependency Readiness Check
@app.get(
    "/ready",
    tags=["System"],
    summary="Readiness Probe",
    description="Verifies essential dependency health (MongoDB) before routing traffic.",
)
async def readiness_check() -> JSONResponse:
    is_mongo_alive = await mongo_manager.ping()
    if is_mongo_alive or settings.USE_MOCK_DB:
        db_label = "mock_fallback" if mongo_manager.is_fallback_mock else "connected"
        payload = {"status": "ready", "database": db_label}
        if mongo_manager.is_fallback_mock:
            payload["note"] = "Operating in in-memory fallback. Live MongoDB connection was unavailable."
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=payload,
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "database": "disconnected"},
    )


# Mount API v1 router
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)
