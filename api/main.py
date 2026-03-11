import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import get_connection
from scheduler import start_scheduler
from routes.auth import router as auth_router

# Logging ayarla
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scheduler instance
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup ve shutdown"""
    global scheduler
    # Startup
    scheduler = start_scheduler()
    logger.info("Application started - scheduler running")
    yield
    # Shutdown
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler shutdown")
from routes.dashboard import router as dashboard_router
from routes.keywords import router as keywords_router
from routes.users import router as users_router
from routes.settings import router as settings_router
from routes.cv import router as cv_router
from routes.candidates import router as candidates_router
from routes.interviews import router as interviews_router
from routes.emails import router as emails_router
from routes.pools import router as pools_router
from routes.companies import router as companies_router
from routes.admin import router as admin_router
from routes.synonyms import router as synonyms_router
from routes.ai_evaluation import router as ai_evaluation_router

app = FastAPI(
    title="HyliAI API",
    version="1.0.0",
    docs_url=None if os.getenv("ENV") == "production" else "/docs",
    redoc_url=None if os.getenv("ENV") == "production" else "/redoc",
    openapi_url=None if os.getenv("ENV") == "production" else "/openapi.json",
    lifespan=lifespan
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://***REMOVED***:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# Router'ları ekle
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(keywords_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(cv_router)
app.include_router(candidates_router)
app.include_router(interviews_router)
app.include_router(emails_router)
app.include_router(pools_router)
app.include_router(companies_router)
app.include_router(admin_router)
app.include_router(synonyms_router)
app.include_router(ai_evaluation_router)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/test/db")
def test_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM candidates")
        count = cursor.fetchone()[0]
    return {"candidate_count": count}
