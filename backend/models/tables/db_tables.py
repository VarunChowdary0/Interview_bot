from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, ForeignKey, JSON
from typing import Optional

class Base(DeclarativeBase):
    pass

class 