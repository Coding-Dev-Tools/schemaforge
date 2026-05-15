"""SchemaForge Demo: Blog Schema (SQLAlchemy Declarative Models)
Convert to any ORM format with: schemaforge convert --from sqlalchemy --to <format> --input fixtures/sample.sqlalchemy.py
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float, Numeric,
    ForeignKey, Enum as SAEnum, func,
)
from sqlalchemy.orm import declarative_base
import enum

Base = declarative_base()


class UserRole(enum.Enum):
    admin = "admin"
    editor = "editor"
    author = "author"
    subscriber = "subscriber"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.subscriber)
    bio = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    excerpt = Column(String(500), nullable=True)
    status = Column(String(20), default="draft")
    published_at = Column(DateTime, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    view_count = Column(Integer, default=0)
    rating = Column(Numeric(3, 2), default=0.00)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
