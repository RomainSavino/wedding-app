import os
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import UPLOAD_DIR
from database import get_db
from models import Guest, Theme, Photo, PhotoArchive
from websocket_manager import manager, projection_manager

router = APIRouter()
ARCHIVE_DIR = os.path.join(UPLOAD_DIR, "archive")
STATE_FILE = "projection_state.json"


# ==========
# Projection state (persisté sur disque)
# ==========

def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"mode": "waiting", "theme_id": None, "duration": 7000}


def _save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


_projection_state: dict = _load_state()


def get_projection_state() -> dict:
    return _projection_state


# ==========
# Auth
# ==========

def require_admin(x_admin_password: str = Header(...)):
    from config import ADMIN_PASSWORD
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe admin incorrect")


# ==========
# WebSocket admin
# ==========

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ==========
# Stats
# ==========

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    themes = db.query(Theme).order_by(Theme.table_number).all()
    return {
        "total_guests":     db.query(Guest).count(),
        "total_photos":     db.query(Photo).count(),
        "selected_photos":  db.query(Photo).filter(Photo.is_selected   == True).count(),
        "projection_photos":db.query(Photo).filter(Photo.is_projection == True).count(),
        "finalist_photos":  db.query(Photo).filter(Photo.is_finalist   == True).count(),
        "themes": [
            {
                "id": t.id, "name": t.name, "emoji": t.emoji,
                "table_number": t.table_number,
                "guest_count":      len(t.guests),
                "photo_count":      len(t.photos),
                "selected_count":   sum(1 for p in t.photos if p.is_selected),
                "projection_count": sum(1 for p in t.photos if p.is_projection),
                "finalist": next(
                    ({"id": p.id,
                      "url": f"/uploads/{p.filename}",
                      "thumbnail_url": f"/uploads/{p.thumbnail_filename}",
                      "guest_name": p.guest.name}
                     for p in t.photos if p.is_finalist), None
                ),
            }
            for t in themes
        ],
    }


# ==========
# Photos
# ==========

def _pd(p: Photo) -> dict:
    return {
        "id": p.id, "guest_id": p.guest_id, "guest_name": p.guest.name,
        "theme_id": p.theme_id, "theme_name": p.theme.name,
        "url": f"/uploads/{p.filename}",
        "thumbnail_url": f"/uploads/{p.thumbnail_filename}",
        "is_selected":   p.is_selected,
        "is_finalist":   p.is_finalist,
        "is_projection": p.is_projection,
        "uploaded_at":   p.uploaded_at.isoformat(),
    }


@router.get("/photos")
def get_all_photos(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    return [_pd(p) for p in db.query(Photo).order_by(Photo.uploaded_at.desc()).all()]


@router.get("/selected")
def get_photos_for_finale(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    themes = db.query(Theme).order_by(Theme.table_number).all()
    result = []
    for theme in themes:
        def sort_key(p):
            if p.is_finalist:   return 0
            if p.is_projection: return 1
            if p.is_selected:   return 2
            return 3
        photos = sorted(theme.photos, key=sort_key)
        result.append({
            "theme_id":    theme.id,
            "theme_name":  theme.name,
            "theme_emoji": theme.emoji,
            "photos":      [_pd(p) for p in photos],
            "finalist_id": next((p.id for p in theme.photos if p.is_finalist), None),
        })
    return result


@router.delete("/photos/{photo_id}")
async def admin_delete_photo(photo_id: int, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    for fname in [photo.filename, photo.thumbnail_filename]:
        if fname:
            path = os.path.join(UPLOAD_DIR, fname)
            if os.path.exists(path): os.remove(path)
    db.delete(photo)
    db.commit()
    await manager.broadcast({"event": "photo_deleted", "photo_id": photo_id})
    return {"deleted": True}


# ==========
# Projection
# ==========

class ProjectionCmd(BaseModel):
    mode: str
    theme_id: int | None = None
    duration: int = 7000


@router.put("/projection")
async def set_projection(cmd: ProjectionCmd, _: None = Depends(require_admin)):
    _projection_state.update(cmd.model_dump())
    _save_state(_projection_state)
    await projection_manager.broadcast({"event": "projection_control", **_projection_state})
    return _projection_state


# ==========
# Archive
# ==========

@router.get("/archive")
def get_archive(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    entries = db.query(PhotoArchive).order_by(PhotoArchive.uploaded_at.desc()).all()
    return [
        {"id": e.id, "guest_name": e.guest_name, "theme_name": e.theme_name,
         "url": f"/uploads/archive/{e.filename}",
         "thumbnail_url": f"/uploads/archive/{e.thumbnail_filename}",
         "uploaded_at": e.uploaded_at.isoformat()}
        for e in entries
    ]


# ==========
# Invités
# ==========

@router.get("/guests")
def admin_list_guests(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    return [
        {"id": g.id, "name": g.name, "table_number": g.table_number,
         "theme_name": g.theme.name, "photo_count": len(g.photos),
         "has_selected": any(p.is_selected for p in g.photos)}
        for g in db.query(Guest).order_by(Guest.table_number, Guest.name).all()
    ]


@router.delete("/guests/{guest_id}")
async def admin_delete_guest(guest_id: int, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Invité introuvable")
    for photo in guest.photos:
        for fname in [photo.filename, photo.thumbnail_filename]:
            if fname:
                path = os.path.join(UPLOAD_DIR, fname)
                if os.path.exists(path): os.remove(path)
        db.delete(photo)
    db.delete(guest)
    db.commit()
    return {"deleted": True}
