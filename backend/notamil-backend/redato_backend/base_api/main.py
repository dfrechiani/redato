import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redato_backend.base_api.api_routes.auth_routes import router as auth_router
from redato_backend.base_api.api_routes.dashboard_routes import router as dashboard_router
from redato_backend.base_api.api_routes.essay_routes import router as essay_router
from redato_backend.base_api.api_routes.intelligence_routes import (
    router as intelligence_router,
)
from redato_backend.base_api.api_routes.manager_routes import router as manager_router
from redato_backend.base_api.api_routes.user_routes import router as user_router
from redato_backend.shared.logger import logger


def _resolve_cors_origins() -> list:
    """Parse CORS_ALLOWED_ORIGINS env var into a list of exact origins.

    - Set CORS_ALLOWED_ORIGINS="https://app.example.com,https://staging.example.com"
      to lock down prod.
    - Set CORS_ALLOWED_ORIGINS="*" to explicitly opt into the wildcard (note:
      wildcard is incompatible with allow_credentials=True in browsers).
    - Leave unset to keep the legacy wildcard with a warning — do not ship that
      to prod.
    """
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if not raw:
        logger.warning(
            "CORS_ALLOWED_ORIGINS is not set. Falling back to wildcard '*' — "
            "set this env var in production."
        )
        return ["*"]
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if origins == ["*"]:
        return ["*"]
    return origins


def create_application() -> FastAPI:
    app = FastAPI(
        title="Redato API",
        description="API for back-end of Redato software.",
        version="1.0.0",
    )

    origins = _resolve_cors_origins()
    # allow_credentials only works with explicit origins, not the wildcard.
    allow_credentials = origins != ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(essay_router)
    app.include_router(dashboard_router)
    app.include_router(intelligence_router)
    app.include_router(manager_router)
    return app


app = create_application()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
