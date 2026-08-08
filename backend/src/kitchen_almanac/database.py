from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from kitchen_almanac.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str | None = None, **engine_options):
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, **engine_options)
    if url.startswith("sqlite"):
        event.listen(
            engine,
            "connect",
            lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
        )
    return engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
