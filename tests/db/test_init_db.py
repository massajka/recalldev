from src.db.db import init_db, engine
from sqlmodel import inspect


def test_init_db_creates_tables():
    init_db()
    insp = inspect(engine)
    # minimal sanity: check at least ProgrammingLanguage table exists
    assert "programminglanguage" in insp.get_table_names()
