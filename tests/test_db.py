import logging

import pytest
from sqlmodel import inspect

from src.db import db as db_module
from src.db import services
from src.db.db import engine, get_session, init_db


# ---------------- init_db behaviours -----------------


def test_init_db_exception(monkeypatch, caplog):
    caplog.set_level("ERROR")

    def boom(*args, **kwargs):
        raise RuntimeError("fail create")

    monkeypatch.setattr(db_module.SQLModel.metadata, "create_all", boom, raising=True)

    db_module.init_db()  # should not raise

    assert any(
        "CRITICAL" in r.message or "fail create" in r.message for r in caplog.records
    )


# ---------------- get_session context manager ---------


def test_get_session_context_manager():
    with get_session() as s:
        services.get_or_create_language(s, name="Rust", slug="rust")

    with get_session() as s2:
        lang = services.get_language_by_slug(s2, "rust")
        assert lang and lang.name == "Rust"
