import os
import uuid
import shutil
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from PIL import Image

from config import UPLOAD_DIR, MAX_IMAGE_SIZE, THUMBNAIL_SIZE, IMAGE_QUALITY, THUMBNAIL_QUALITY
from database import get_db
from models import Photo, Guest, PhotoArchive
from websocket_manager import manager

router = APIRouter()
ARCHIVE_DIR = os.path.join(UPLOAD_DIR, "archive")


# ==========
# Helpers
# ==========

def _save_image(content: bytes, filename: str) -> str:
    image = Image.open(BytesIO(content))
    if image.mode in ("RGBA", "P", "LA"):
        image = image.convert("RGB")
    image.thumbnail(MAX_IMAGE_SIZE, Image.LANCZOS)
    image.save(os.path.join(UPLOAD_DIR, filename), "JPEG", quality=IMAGE_QUALITY, optimize=True)
    thumb = image.copy()
    thumb.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
    thumb_name = f"thumb_{filename}"
    thumb.save(os.path.join(UPLOAD_DIR, thumb_name), "JPEG", quality=THUMBNAIL_QUALITY)
    return thumb_name


def _pd(p: Photo) -> dict:
    return {
        "id": p.id, "guest_id": p.guest_id, "guest_name": p.guest.name,
        "theme_id": p.theme_id,
        "url": f"/uploads/{p.filename}",
        "thumbnail_url": f"/uploads/{p.thumbnail_filename}",
        "is_selected": p.is_selected,
        "is_finalist": p.is_finalist,
        "is_projection": p.is_projection,
        "uploaded_at": p.uploaded_at.isoformat(),
    }


# ==========
# Routes
# ==========

@router.post("/upload")
async def upload_photo(guest_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Invité introuvable")
    content = await file.read()
    filename = f"{uuid.uuid4()}.jpg"
    thumb_name = _save_image(content, filename)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    shutil.copy2(os.path.join(UPLOAD_DIR, filename), os.path.join(ARCHIVE_DIR, filename))
    shutil.copy2(os.path.join(UPLOAD_DIR, thumb_name), os.path.join(ARCHIVE_DIR, thumb_name))
    photo = Photo(guest_id=guest.id, theme_id=guest.theme_id, filename=filename, thumbnail_filename=thumb_name)
    db.add(photo)
    db.flush()
    db.add(PhotoArchive(
        original_photo_id=photo.id, guest_name=guest.name,
        theme_id=guest.theme_id, theme_name=guest.theme.name,
        filename=filename, thumbnail_filename=thumb_name, uploaded_at=photo.uploaded_at,
    ))
    db.commit()
    db.refresh(photo)
    await manager.broadcast({"event": "new_photo", "photo": _pd(photo)})
    return _pd(photo)


@router.get("")
@router.get("/")
def get_photos(theme_id: int = None, guest_id: int = None, db: Session = Depends(get_db)):
    q = db.query(Photo)
    if theme_id is not None: q = q.filter(Photo.theme_id == theme_id)
    if guest_id is not None: q = q.filter(Photo.guest_id == guest_id)
    return [_pd(p) for p in q.order_by(Photo.uploaded_at.desc()).all()]


@router.put("/{photo_id}/select")
async def select_photo(photo_id: int, guest_id: int, db: Session = Depends(get_db)):
    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.guest_id == guest_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    db.query(Photo).filter(Photo.guest_id == guest_id, Photo.id != photo_id).update({"is_selected": False})
    photo.is_selected = not photo.is_selected
    db.commit()
    await manager.broadcast({"event": "photo_selected", "photo_id": photo_id, "guest_id": guest_id,
                              "theme_id": photo.theme_id, "is_selected": photo.is_selected})
    return {"id": photo.id, "is_selected": photo.is_selected}


@router.put("/{photo_id}/finalist")
async def toggle_finalist(photo_id: int, db: Session = Depends(get_db)):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    db.query(Photo).filter(Photo.theme_id == photo.theme_id, Photo.id != photo_id).update({"is_finalist": False})
    photo.is_finalist = not photo.is_finalist
    db.commit()
    await manager.broadcast({"event": "finalist_changed", "photo_id": photo_id,
                              "theme_id": photo.theme_id, "is_finalist": photo.is_finalist})
    return {"id": photo.id, "is_finalist": photo.is_finalist}


@router.put("/{photo_id}/projection")
async def toggle_projection(photo_id: int, db: Session = Depends(get_db)):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    photo.is_projection = not photo.is_projection
    db.commit()
    await manager.broadcast({"event": "projection_changed", "photo_id": photo_id,
                              "theme_id": photo.theme_id, "is_projection": photo.is_projection})
    return {"id": photo.id, "is_projection": photo.is_projection}


@router.delete("/{photo_id}")
async def delete_photo(photo_id: int, guest_id: int, db: Session = Depends(get_db)):
    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.guest_id == guest_id).first()
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
