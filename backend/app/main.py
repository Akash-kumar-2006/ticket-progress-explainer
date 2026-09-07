"""FastAPI application entry point.

Run with:
  uvicorn app.main:app --reload

OpenAPI documentation is generated automatically at /docs.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import PROJECT_ROOT, settings
from .database import create_all

app = FastAPI(
    title="Ticket Progress Explanation Generator",
    description=(
        "Evidence-grounded progress explanation engine for customer tickets that are "
        "transferred between regional support teams. Generates customer-facing "
        "explanations strictly from ticket events, dependencies, approvals, vendor "
        "updates and promised dates - no invented facts."
    ),
    version=settings.model_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


app.on_event("startup")
def on_startup():
    create_all()


_FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    # Production single-server mode: serve the built React app from FastAPI.
    # Client-side routes fall back to index.html; /api/* stays on the API.
    _assets = _FRONTEND_DIST / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def _spa_fallback(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(_FRONTEND_DIST / "index.html")