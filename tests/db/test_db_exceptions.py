import logging
from src.db import db as db_module


def test_init_db_exception(monkeypatch, caplog):
    caplog.set_level("ERROR")

    def boom(*args, **kwargs):
        raise RuntimeError("fail create")

    monkeypatch.setattr(db_module.SQLModel.metadata, "create_all", boom, raising=True)

    # Should not raise but log exception
    db_module.init_db()

    assert any("CRITICAL" in r.message for r in caplog.records)
