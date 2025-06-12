import types
import sys, pathlib

# Ensure project src/ is importable
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from types import SimpleNamespace
from sqlmodel import SQLModel, Session, create_engine

# --- Pytest fixtures ---

@pytest.fixture(scope="session")
def engine():
    # In-memory SQLite for speed; disable thread check for async tests
    return create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})


@pytest.fixture(autouse=True)
def _apply_test_engine(engine, monkeypatch):
    """Patch project-wide engine & get_session to use the in-memory engine."""
    from src.db import db as db_module

    # Override engine
    monkeypatch.setattr(db_module, "engine", engine, raising=False)

    # Patch get_session to use engine from fixture
    from contextlib import contextmanager

    @contextmanager
    def _get_session():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(db_module, "get_session", _get_session, raising=False)
    # services import get_session from db at runtime; ensure it also uses patched one
    import src.db.services as services_module
    monkeypatch.setattr(services_module, "get_session", _get_session, raising=False)

    # Create tables once per session
    SQLModel.metadata.create_all(engine)


@pytest.fixture
def session(engine):
    """Provide a fresh DB session for each test."""
    with Session(engine) as s:
        yield s
        s.rollback()


@pytest.fixture
def fake_llm(monkeypatch):
    """Stub for LangChain ChatModel.invoke returning deterministic text."""
    class _FakeChat:
        def invoke(self, messages):
            return types.SimpleNamespace(content="FAKE_EXPLANATION")

    chat_model = _FakeChat()
    # Provide this model via context.bot_data in tests
    return chat_model


@pytest.fixture
def test_context(fake_llm):
    """Return a minimal stand-in for telegram.ext.ContextTypes.DEFAULT_TYPE."""
    ctx = SimpleNamespace()
    ctx.user_data = {}
    ctx.bot_data = {"chat_model": fake_llm}
    return ctx


# --- Sample data fixture -------------------------------------------------

@pytest.fixture
def sample_questions(session):
    """Create a language, category and two diagnostic + two practice questions.

    Returns a SimpleNamespace with attributes:
        lang, cat, diag_q, diag_q2, q1, q2, user
    """
    from src.db import services
    from types import SimpleNamespace

    lang = services.get_or_create_language(session, name="Python", slug="python")
    cat = services.get_or_create_category(session, name="Basics")

    # Diagnostic
    diag_q = services.create_question(
        session,
        text="Diag 1?",
        category_id=cat.id,
        language_id=lang.id,
        is_diagnostic=True,
    )
    diag_q2 = services.create_question(
        session,
        text="Diag 2?",
        category_id=cat.id,
        language_id=lang.id,
        is_diagnostic=True,
    )

    # Practice
    q1 = services.create_question(session, text="What is Python?", category_id=cat.id, language_id=lang.id)
    q2 = services.create_question(session, text="Explain list comprehension", category_id=cat.id, language_id=lang.id)

    user = services.get_or_create_user(session, telegram_id=123)
    services.set_user_active_language(session, user.id, lang.id)

    return SimpleNamespace(
        lang=lang,
        cat=cat,
        diag_q=diag_q,
        diag_q2=diag_q2,
        q1=q1,
        q2=q2,
        user=user,
    )
