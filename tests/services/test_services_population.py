from src.db import services
from src.db.db import get_session
from sqlmodel import select


def test_populate_initial_data(session):
    # populate
    services.populate_initial_data(session)

    langs = session.exec(select(services.ProgrammingLanguage)).all()
    cats = session.exec(select(services.Category)).all()
    qs = session.exec(select(services.Question)).all()

    assert len(langs) >= 3
    assert len(cats) >= 3
    assert any(q.is_diagnostic for q in qs)
