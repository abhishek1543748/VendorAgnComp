from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from app.core.db import engine
from app.api.devices import router as devices_router
from app.api.parse import router as parse_router
from app.api.frameworks import router as frameworks_router
from app.api.findings import router as findings_router
from app.api.reports import router as reports_router
import app.models.tables  # Ensures SQLModel table models are registered

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(title="Compliance Engine API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices_router)
app.include_router(parse_router)
app.include_router(frameworks_router)
app.include_router(findings_router)
app.include_router(reports_router)

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Compliance Engine API",
        "docs": "http://127.0.0.1:8000/docs",
        "devices_endpoint": "http://127.0.0.1:8000/devices"
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}



