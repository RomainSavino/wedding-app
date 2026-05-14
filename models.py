from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Theme(Base):
    __tablename__ = "themes"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    table_number = Column(Integer, nullable=False, unique=True)
    description = Column(String, nullable=False)
    emoji = Column(String, default="📸")
    guests = relationship("Guest", back_populates="theme")
    photos = relationship("Photo", back_populates="theme")


class Guest(Base):
    __tablename__ = "guests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    table_number = Column(Integer, nullable=False)
    theme_id = Column(Integer, ForeignKey("themes.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    theme = relationship("Theme", back_populates="guests")
    photos = relationship("Photo", back_populates="guest")


class Photo(Base):
    __tablename__ = "photos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    guest_id = Column(Integer, ForeignKey("guests.id"), nullable=False)
    theme_id = Column(Integer, ForeignKey("themes.id"), nullable=False)
    filename = Column(String, nullable=False)
    thumbnail_filename = Column(String, nullable=True)
    is_selected = Column(Boolean, default=False)    # choix de l'invité
    is_finalist = Column(Boolean, default=False)    # finaliste par thème (grande finale)
    is_projection = Column(Boolean, default=False)  # choix admin pour la projection
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    guest = relationship("Guest", back_populates="photos")
    theme = relationship("Theme", back_populates="photos")


class PhotoArchive(Base):
    __tablename__ = "photos_archive"
    id = Column(Integer, primary_key=True, autoincrement=True)
    original_photo_id = Column(Integer, nullable=False)
    guest_name = Column(String, nullable=False)
    theme_id = Column(Integer, nullable=False)
    theme_name = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    thumbnail_filename = Column(String, nullable=True)
    uploaded_at = Column(DateTime, nullable=False)
    archived_at = Column(DateTime, default=datetime.utcnow)
