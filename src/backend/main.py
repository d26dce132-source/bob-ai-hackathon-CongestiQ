"""
CongestiQ — FastAPI application entry point.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.init_db import init_db
from routers import (
    assignments,
    berths,
    congestion,
    cranes,
    health,
    operations_plan,
    routing,
    schedules,
    vessel_risk,
    vessels,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup logic (table creation + seeding) before accepting requests."""
    init_db()
    yield
    # Shutdown logic can be added here if needed


app = FastAPI(
    title="CongestiQ API",
    description=(
        "AI-Powered Port Congestion Prediction & Operations Optimizer.\n\n"
        "Phase 3: Berth/crane assignment optimization, alternative routing, and 72-hour operations plan added."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow the React dev server and any configured origins
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
API_PREFIX = "/api"

app.include_router(health.router, prefix=API_PREFIX)
# vessel_risk MUST come before vessels so /vessels/risk is matched before /vessels/{id}
app.include_router(vessel_risk.router, prefix=API_PREFIX)
app.include_router(vessels.router, prefix=API_PREFIX)
app.include_router(berths.router, prefix=API_PREFIX)
app.include_router(cranes.router, prefix=API_PREFIX)
app.include_router(schedules.router, prefix=API_PREFIX)
app.include_router(congestion.router, prefix=API_PREFIX)
app.include_router(assignments.router, prefix=API_PREFIX)
app.include_router(routing.router, prefix=API_PREFIX)
app.include_router(operations_plan.router, prefix=API_PREFIX)


# ---------------------------------------------------------------------------
# Root redirect to docs
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
