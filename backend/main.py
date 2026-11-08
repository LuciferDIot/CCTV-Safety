"""FastAPI entrypoint for AURA-Traffic CCTV Motorcycle Safety Backend."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings
from controllers.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    settings = get_settings()
    print(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    print(f"Monorepo Root: {settings.project_root}")
    yield
    print("Shutting down AURA-Traffic backend service.")


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for Motorcycle Wrong-Way & Crosswalk Safety Analyzer",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/", tags=["root"])
def root_redirect():
    return {
        "service": settings.app_name,
        "status": "online",
        "docs": "/docs",
        "api": "/api/health"
    }

