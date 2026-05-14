from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import Guest, Theme

router = APIRouter()


# ==========
# Schemas
# ==========

class GuestRegisterRequest(BaseModel):
    name: str
    table_number: int


def _guest_to_dict(guest: Guest) -> dict:
    return {
        "id": guest.id,
        "name": guest.name,
        "table_number": guest.table_number,
        "theme_id": guest.theme_id,
        "theme_name": guest.theme.name,
        "theme_description": guest.theme.description,
        "theme_emoji": guest.theme.emoji,
        "created_at": guest.created_at.isoformat(),
    }


# ==========
# Routes
# ==========

@router.post("/register")
def register_guest(data: GuestRegisterRequest, response: Response, db: Session = Depends(get_db)):
    theme = db.query(Theme).filter(Theme.table_number == data.table_number).first()
    if not theme:
        raise HTTPException(status_code=404, detail=f"Table {data.table_number} introuvable")

    existing = db.query(Guest).filter(
        Guest.name == data.name,
        Guest.table_number == data.table_number
    ).first()

    if existing:
        guest = existing
    else:
        guest = Guest(name=data.name, table_number=data.table_number, theme_id=theme.id)
        db.add(guest)
        db.commit()
        db.refresh(guest)

    response.set_cookie(
        key="guest_id",
        value=str(guest.id),
        max_age=86400 * 7,
        httponly=False,
        samesite="lax",
    )

    return _guest_to_dict(guest)


@router.get("")
@router.get("/")
def list_guests(db: Session = Depends(get_db)):
    guests = db.query(Guest).order_by(Guest.created_at.asc()).all()
    return [_guest_to_dict(g) for g in guests]


@router.get("/{guest_id}")
def get_guest(guest_id: int, db: Session = Depends(get_db)):
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Invité introuvable")
    return _guest_to_dict(guest)
