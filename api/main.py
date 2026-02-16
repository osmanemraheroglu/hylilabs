from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import get_connection
from routes.auth import router as auth_router
from routes.dashboard import router as dashboard_router
from routes.keywords import router as keywords_router
from routes.users import router as users_router
from routes.settings import router as settings_router
from routes.cv import router as cv_router

app = FastAPI(title="HyliAI API", version="1.0.0")

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://***REMOVED***:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları ekle
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(keywords_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(cv_router)

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
