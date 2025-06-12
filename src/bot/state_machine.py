from enum import Enum
from sqlmodel import select, Session
from src.db.models import User
from typing import Optional

class UserState(Enum):
    LANG_SELECT = "lang_select"
    DIAGNOSTICS = "diagnostics"
    PRACTICE = "practice"
    WAITING_FOR_ANSWER = "waiting_for_answer"
    END = "end"

def get_user_state(session: Session, telegram_id: int) -> str:
    user = session.exec(select(User).where(User.telegram_id == telegram_id)).first()
    return getattr(user, 'state', UserState.LANG_SELECT.value) if user else UserState.LANG_SELECT.value

def set_user_state(session: Session, telegram_id: int, state: str|UserState) -> None:
    user = session.exec(select(User).where(User.telegram_id == telegram_id)).first()
    if user:
        user.state = state.value if isinstance(state, UserState) else state
        session.add(user)
        session.commit()

# Helper functions

def is_in_state(session: Session, telegram_id: int, state: str|UserState) -> bool:
    current = get_user_state(session, telegram_id)
    check = state.value if isinstance(state, UserState) else state
    return current == check

def set_state_and_log(session: Session, telegram_id: int, state: str|UserState, reason: Optional[str]=None):
    set_user_state(session, telegram_id, state)
    logger.info(f"[STATE] User {telegram_id} set to {state} ({reason or ''})")
