import logging
from src.bot import state_machine as sm
from src.db import services


def test_set_state_and_log(session, caplog):
    logging.root.setLevel("INFO")
    caplog.set_level("INFO")
    user = services.get_or_create_user(session, telegram_id=9999)
    sm.set_state_and_log(session, user.telegram_id, sm.UserState.END, reason="tests")
    assert any("STATE" in rec.message for rec in caplog.records)
    assert sm.is_in_state(session, user.telegram_id, sm.UserState.END)
