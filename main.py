import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from config import UPLOAD_DIR
from database import engine, Base, SessionLocal, DB_PATH
from models import Theme
from routes import guests, photos, themes, admin, projection

# git add main.py ; git commit -m '[WIP] Nom des tables' ; git push
# ==========
# Seed
# ==========

THEMES_SEED = [
    {"id": 1, "name": "Table Fondcombe", "table_number": 1, "description": "La -meilleure- table des mariés..", "emoji": "💕"},
    {"id": 2, "name": "Table Mordor", "table_number": 2, "description": "La table des oncles et tantes... Personne veut y aller", "emoji": "🎉"},
    {"id": 3, "name": "Table 3", "table_number": 3, "description": "Objectif photo de la Table 3", "emoji": "📸"},
    {"id": 4, "name": "Table 4", "table_number": 4, "description": "Objectif photo de la Table 4", "emoji": "🥂"},
    {"id": 5, "name": "Table 5", "table_number": 5, "description": "Objectif photo de la Table 5", "emoji": "🌸"},
    {"id": 6, "name": "Table 6", "table_number": 6, "description": "Objectif photo de la Table 6", "emoji": "🎊"},
    {"id": 7, "name": "Table 7", "table_number": 7, "description": "Objectif photo de la Table 7", "emoji": "✨"},
    {"id": 8, "name": "Photos Audrey", "table_number": 8, "description": "Rétrospective de la vie de Sarah...", "emoji": "✨"},
]


# ==========
# Migration & seed
# ==========

def _migrate():
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE photos ADD COLUMN is_finalist BOOLEAN DEFAULT 0",
            "ALTER TABLE photos ADD COLUMN is_projection BOOLEAN DEFAULT 0",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass

    db = SessionLocal()
    try:
        existing_ids = {t.id for t in db.query(Theme).all()}
        for seed in THEMES_SEED:
            if seed["id"] not in existing_ids:
                db.add(Theme(**seed))

        for seed in THEMES_SEED:
            t = db.query(Theme).filter(Theme.id == seed["id"]).first()
            if t:
                t.name        = seed["name"]
                t.description = seed["description"]
                t.emoji       = seed["emoji"]

        db.commit()
    finally:
        db.close()


# ==========
# Lifespan
# ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate()
    yield


# ==========
# Dossiers (niveau module, avant app.mount)
# ==========

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "archive"), exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


# ==========
# App
# ==========

app = FastAPI(title="Wedding App", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

app.include_router(guests.router,     prefix="/api/guests",     tags=["guests"])
app.include_router(photos.router,     prefix="/api/photos",     tags=["photos"])
app.include_router(themes.router,     prefix="/api/themes",     tags=["themes"])
app.include_router(admin.router,      prefix="/api/admin",      tags=["admin"])
app.include_router(projection.router, prefix="/api/projection", tags=["projection"])

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ==========
# Frontend
# ==========

@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}

@app.get("/admin.html",       include_in_schema=False)
async def admin_page():       return FileResponse("frontend/admin.html")

@app.get("/projection.html",  include_in_schema=False)
async def projection_page():  return FileResponse("frontend/projection.html")

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_index(full_path: str): return FileResponse("frontend/index.html")