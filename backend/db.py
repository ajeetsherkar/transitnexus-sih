import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./transitnexus.db",
)


class Base(DeclarativeBase):
    pass


connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    from sqlalchemy.orm import Session

    db = Session(engine)
    try:
        yield db
    finally:
        db.close()
