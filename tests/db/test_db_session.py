from src.db.db import get_session
from src.db import services


def test_get_session_context_manager():
    # create entity inside context
    with get_session() as s:
        services.get_or_create_language(s, name="Rust", slug="rust")

    # new context should see persisted record
    with get_session() as s2:
        lang = services.get_language_by_slug(s2, "rust")
        assert lang is not None and lang.name == "Rust"
