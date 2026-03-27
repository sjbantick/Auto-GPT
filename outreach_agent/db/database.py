from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from outreach_agent.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from outreach_agent.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
