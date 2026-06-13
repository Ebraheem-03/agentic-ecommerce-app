"""FastAPI application entrypoint.

US-E4-00 (CONTRACT DRAFT): mounts the full route inventory (auth, catalog, search,
cart, orders, returns, agent, seller, admin) with Pydantic v2 request/response models
and the shared success/error envelope. Route handlers are deliberate stubs that 501 —
this is a contract preview so the rendered API reference can be reviewed before any
business logic exists.

Docs are served with **Scalar** (house standard, CLAUDE.md §7) at ``/docs``; FastAPI's
default Swagger UI + ReDoc are disabled. The raw OpenAPI document is at ``/openapi.json``.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from scalar_fastapi import get_scalar_api_reference

from app.api.routers import (
    admin,
    agent,
    auth,
    cart,
    catalog,
    orders,
    returns,
    search,
    seller,
)

app = FastAPI(
    title="Hearth — Agentic E-Commerce API",
    version="0.1.0-contract",
    summary="CONTRACT DRAFT (US-E4-00). Handlers are not implemented (501).",
    # Disable default Swagger UI + ReDoc; we serve Scalar at /docs (see below).
    docs_url=None,
    redoc_url=None,
)


class HealthResponse(BaseModel):
    """Response body for the health check."""

    status: str


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Liveness probe used by Docker, CI, and deploy targets."""
    return HealthResponse(status="ok")


@app.get("/docs", include_in_schema=False)
def scalar_docs() -> HTMLResponse:
    """Serve the Scalar API reference for the contract (not Swagger UI)."""
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


# Route inventory — one router per resource group.
for _router in (
    auth.router,
    catalog.router,
    search.router,
    cart.router,
    orders.router,
    returns.router,
    agent.router,
    seller.router,
    admin.router,
):
    app.include_router(_router)
