from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import get_connection

app = FastAPI(title="HyliAI API", version="1.0.0")

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://***REMOVED***:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
