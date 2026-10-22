import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import OperationalError, DBAPIError
from app.core.config import settings
from app.api.tickets import router as tickets_router
from app.api.mock_crm import router as mock_crm_router
from app.api.workflow_runs import router as workflow_runs_router

logger = logging.getLogger("flowforge.api")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API and Data Contracts for FlowForge AI",
    version=settings.VERSION,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    sanitized_errors = []
    for err in exc.errors():
        loc = list(err.get("loc", []))
        if loc and loc[0] in ("body", "query", "path"):
            loc = loc[1:]
        field_name = ".".join(str(x) for x in loc) if loc else "payload"
        sanitized_errors.append({
            "field": field_name,
            "type": err.get("type"),
            "msg": err.get("msg"),
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": sanitized_errors},
    )


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    logger.error("Database operational error: %s", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database service is temporarily unavailable. Please retry shortly."},
    )


@app.exception_handler(DBAPIError)
async def db_generic_error_handler(request: Request, exc: DBAPIError):
    logger.error("Database transaction error: %s", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred while processing the request."},
    )


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "service": "flowforge-core",
        "version": "0.1.0",
    }


app.include_router(tickets_router, prefix="/api")
app.include_router(mock_crm_router, prefix="/api")
app.include_router(workflow_runs_router, prefix="/api")
