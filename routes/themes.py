from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Theme

router = APIRouter()


# ==========
# Helpers
# ==========

def _theme_to_dict(theme: Theme, include_photos: bool = False) -> dict:
    data = {
        "id":            theme.id,
        "name":          theme.name,
        "table_number":  theme.table_number,
        "description":   theme.description,
        "emoji":         theme.emoji,
        "guest_count":   len(theme.guests),
        "photo_count":   len(theme.photos),
        "selected_count":   sum(1 for p in theme.photos if p.is_selected),
        "projection_count": sum(1 for p in theme.photos if p.is_projection),
        "finalist_count":   sum(1 for p in theme.photos if p.is_finalist),
    }

    if include_photos:
        data["photos"] = [
            {
                "id":             p.id,
                "guest_name":     p.guest.name,
                "url":            f"/uploads/{p.filename}",
                "thumbnail_url":  f"/uploads/{p.thumbnail_filename}",
                "is_selected":    p.is_selected,
                "is_projection":  p.is_projection,
                "is_finalist":    p.is_finalist,
                "uploaded_at":    p.uploaded_at.isoformat(),
            }
            for p in sorted(theme.photos, key=lambda x: x.uploaded_at, reverse=True)
        ]

    return data


# ==========
# Routes
# ==========

@router.get("")
@router.get("/")
def list_themes(db: Session = Depends(get_db)):
    themes = db.query(Theme).order_by(Theme.table_number).all()
    return [_theme_to_dict(t) for t in themes]


@router.get("/{theme_id}")
def get_theme(theme_id: int, db: Session = Depends(get_db)):
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Thème introuvable")
    return _theme_to_dict(theme, include_photos=True)
