"""FastAPI application entrypoint.

Intentionally thin for the scaffold: exposes a single health endpoint so the
container and CI foundation can be built and exercised before the real API lands.
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Agentic AI E-Commerce API",
    version="0.1.0",
)


class HealthResponse(BaseModel):
    """Response body for the health check."""

    status: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe used by Docker, CI, and deploy targets."""
    return HealthResponse(status="ok")
