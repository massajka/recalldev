from src.bot import state_machine as sm
from src.db import services


def test_state_crud(session):
    user = services.get_or_create_user(session, telegram_id=999)

    # default
    assert sm.get_user_state(session, 999) == sm.UserState.LANG_SELECT.value
    assert sm.is_in_state(session, 999, sm.UserState.LANG_SELECT)

    # set state
    sm.set_user_state(session, 999, sm.UserState.DIAGNOSTICS)
    assert sm.get_user_state(session, 999) == sm.UserState.DIAGNOSTICS.value
    assert sm.is_in_state(session, 999, sm.UserState.DIAGNOSTICS)
