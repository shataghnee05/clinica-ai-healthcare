import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.logger import log_event
from app.routes import api_router
from app.routes_phase2b import phase2b_router

from app.models import engine, Base, run_schema_migrations

@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("APP_STARTUP", {"version": settings.VERSION, "project": settings.PROJECT_NAME})
    try:
        Base.metadata.create_all(bind=engine)
        run_schema_migrations()
    except Exception as e:
        log_event("DB_INIT_WARNING", {"error": str(e)})
    yield
    log_event("APP_SHUTDOWN", {})


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(phase2b_router, prefix=settings.API_V1_STR)

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
        return None
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Healthcare Appointment API is running."}
