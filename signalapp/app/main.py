"""
FastAPI application entry point.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from signalapp.app.config import get_config
from signalapp.db.repository import init_db

logger = logging.getLogger(__name__)


def _setup_gcp_credentials():
    """Write GCP service account JSON from env var to file (for Railway/Cloud deployments)."""
    import os, json
    creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if creds_json and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        creds_path = "/tmp/gcp-service-account.json"
        try:
            # Validate it's real JSON
            json.loads(creds_json)
            with open(creds_path, "w") as f:
                f.write(creds_json)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
            logger.info("[startup] GCP credentials written to %s", creds_path)
        except Exception as e:
            logger.error("[startup] Failed to write GCP credentials: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    _setup_gcp_credentials()
    config = get_config()
    if config.db_url:
        await init_db(config.db_url)
        logger.info("[startup] Database initialized: %s", config.db_url)
    else:
        logger.warning("[startup] No database URL — DB layer disabled")
    yield
    logger.info("[shutdown] Application shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_config()

    app = FastAPI(
        title="Signal Intelligence API",
        description="Post-call behavioral intelligence platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if config.environment == "development" else None,
        redoc_url="/redoc" if config.environment == "development" else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    from signalapp.api.calls import router as calls_router
    from signalapp.api.insights import router as insights_router

    app.include_router(calls_router, prefix="/api/v1/calls", tags=["calls"])
    app.include_router(insights_router, prefix="/api/v1/insights", tags=["insights"])

    # Health check
    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": "0.1.0"}

    # Error handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    return app


# Application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = get_config()
    uvicorn.run(
        "signalapp.app.main:app",
        host=config.api_host,
        port=config.api_port,
        reload=config.debug_mode,
    )
