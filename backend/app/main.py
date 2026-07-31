from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="Security analytics and SOAR simulation platform integrating "
    "threat intelligence feeds, AI-assisted alert analysis, and automated "
    "incident response workflows.",
    version="0.1.0",
)

# Permissive CORS for local dev — tighten before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health_check():
    """Basic liveness check used by Docker Compose / uptime checks."""
    return {"status": "ok", "service": settings.APP_NAME, "environment": settings.ENVIRONMENT}


@app.get("/", tags=["system"])
async def root():
    return {"message": f"{settings.APP_NAME} API — see /docs for the API reference."}
