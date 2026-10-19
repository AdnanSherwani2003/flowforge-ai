from fastapi import FastAPI

app = FastAPI(
    title="FlowForge AI Core",
    description="Backend API for FlowForge AI",
    version="0.1.0",
)


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "service": "flowforge-core",
        "version": "0.1.0",
    }
