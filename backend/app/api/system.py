"""Cheap readiness and authenticated optional-dependency diagnostics."""
import asyncio
import httpx
from fastapi import APIRouter, Depends, Response
from app.core.database import check_database_health
from app.core.config import settings
from app.core.reviewer_auth import reviewer
from app.services.ollama_client import _bounded_json, UpstreamFailure

router = APIRouter(tags=["System"])


@router.get("/ready")
def readiness(response: Response):
    ready = check_database_health()
    response.status_code = 200 if ready else 503
    response.headers["Cache-Control"] = "no-store"
    if not ready:
        response.headers["Retry-After"] = "2"
    return {"status": "ready" if ready else "unavailable",
            "database": "available" if ready else "unavailable"}


@router.get("/api/reviewer/dependencies")
async def dependencies(user: str = Depends(reviewer)):
    # Optional AI never determines readiness for intake, reviews or reports.
    if not settings.ENRICHMENT_ENABLED:
        return {"ollama": "disabled", "required_for_readiness": False}
    try:
        async with asyncio.timeout(2):
            async with httpx.AsyncClient(timeout=1.5, follow_redirects=False) as client:
                value = await _bounded_json(client, "GET", "/api/tags")
        models = value.get("models")
        available = isinstance(models, list) and any(isinstance(m, dict) and m.get("name") == settings.OLLAMA_MODEL
                        and m.get("digest") == settings.OLLAMA_MODEL_DIGEST
                        and not m.get("remote_host")
                        for m in models)
        state = "available" if available else "model_unavailable"
    except (TimeoutError, httpx.HTTPError, UpstreamFailure, TypeError):
        state = "unavailable"
    return {"ollama": state, "required_for_readiness": False}
