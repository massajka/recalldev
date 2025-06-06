import logging
import os
from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager
from .models import (
    ProgrammingLanguage,
    User,
    Category,
    Question,
    UserProgress,
    UserLearningPlanItem,
    UserAnswer
)

logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///db.sqlite3"
engine = create_engine(DATABASE_URL, echo=True)

@contextmanager
def get_session():
    with Session(engine) as session:
        yield session

def init_db():
    """
    Initializes the database by ensuring all tables defined in the models
    are created if they do not already exist. This function does NOT
    delete any existing database or tables. Deletion is handled by drop_db.py.
    """
    logger.info(f"Initializing database ({DATABASE_URL}): Ensuring all tables exist...")
    try:
        # SQLModel.metadata.create_all(engine) will create tables for all imported models
        # that inherit from SQLModel and have `table=True` if they don't already exist.
        # It will not alter existing tables if their schema has changed (that requires migrations).
        SQLModel.metadata.create_all(engine)
        logger.info("Database initialization complete (tables created or verified to exist).")
    except Exception as e:
        logger.exception("CRITICAL: Exception occurred during database table creation/verification in init_db.")
        # Consider re-raising the exception if the application cannot run without a DB
        # raise
