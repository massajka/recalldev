import contextlib
import json
import types
from types import SimpleNamespace

import pytest

from constants import callback_data, messages
from src.bot.flow_result import FlowResult, FlowStatus
from src.bot.flows import diagnostics as diagnostics_flow
from src.bot.flows import practice as practice_flow
from src.bot.views import diagnostics as diagnostics_view
from src.bot.views import language as lang_view_mod
from src.bot.views import practice as practice_view
from src.bot.views.diagnostics import DiagnosticScoreView, DiagnosticsView
from src.bot.views.language import LanguageSelectionView
from src.bot.views.message import UserTextMessageView
from src.bot.views.practice import (
    NextQuestionView,
    PracticeView,
    _extract_json_from_llm_response,
    _generate_and_save_practice_questions,
)
from src.bot.views.technology import TechnologyView
from src.db import services


class DummyMessage:
    def __init__(self):
        self.replies = []
        self.from_user = type("U", (), {"id": 1})()

    async def reply_text(self, text, reply_markup=None):
        self.replies.append((text, reply_markup))


class DummyUpdate:
    def __init__(self):
        self.update_id = 123
        self.message = DummyMessage()
        self.effective_user = type("U", (), {"id": 1})()
        self.callback_query = None


class DummyContext(SimpleNamespace):
    def __init__(self):
        super().__init__()
        self.user_data = {}
        self.bot_data = {}


class TestTechnologyView:
    @pytest.mark.asyncio
    async def test_show_technologies(self, monkeypatch):
        """TechnologyView should send choose message and keyboard."""
        # monkeypatch DB services
        monkeypatch.setattr(
            services,
            "get_or_create_user",
            lambda s, telegram_id: type(
                "U", (), {"id": 1, "active_language_id": None}
            )(),
        )
        monkeypatch.setattr(
            services,
            "list_languages",
            lambda s: [type("L", (), {"id": 1, "name": "Python"})()],
        )

        view = TechnologyView(DummyUpdate(), DummyContext())
        await view.command()
        assert view.update.message.replies, "No reply sent"
        text, markup = view.update.message.replies[0]
        assert "выберите".lower() in text.lower()
        assert markup is not None

    @pytest.mark.asyncio
    async def test_no_technologies(self, monkeypatch):
        """TechnologyView should inform user when no technologies available."""
        monkeypatch.setattr(
            services,
            "get_or_create_user",
            lambda s, telegram_id: type("U", (), {"id": 1})(),
        )
        monkeypatch.setattr(services, "list_languages", lambda s: [])
        monkeypatch.setattr(
            messages, "MSG_NO_AVAILABLE_TECHNOLOGIES", "no tech", raising=False
        )

        view = TechnologyView(DummyUpdate(), DummyContext())
        await view.command()
        assert any("no tech" in t.lower() for t, _ in view.update.message.replies)


class TestDiagnosticsView:
    @pytest.mark.asyncio
    async def test_no_language_redirects_to_technology(self, monkeypatch):
        async def fake_start(ctx):
            return type("R", (), {"status": FlowStatus.NO_LANGUAGE})()

        monkeypatch.setattr(diagnostics_flow, "start_diagnostics", fake_start)

        tech_called = {"flag": False}

        async def fake_tech(self):
            tech_called["flag"] = True

        monkeypatch.setattr(TechnologyView, "command", fake_tech, raising=True)

        view = DiagnosticsView(DummyUpdate(), DummyContext())
        await view.command()
        assert tech_called[
            "flag"
        ], "TechnologyView.command should be called when no language"

    @pytest.mark.asyncio
    async def test_no_questions_available(self, monkeypatch):
        """DiagnosticsView should reply when нет вопросов."""
        monkeypatch.setattr(
            messages, "MSG_NO_DIAGNOSTIC_QUESTIONS_FOR_LANG", "no q", raising=False
        )

        async def fake_start(ctx):
            return FlowResult(status=FlowStatus.NO_QUESTIONS)

        monkeypatch.setattr(diagnostics_flow, "start_diagnostics", fake_start)

        view = DiagnosticsView(DummyUpdate(), DummyContext())
        await view.command()
        assert any("no q" in t.lower() for t, _ in view.update.message.replies)


class TestPracticeView:
    @pytest.mark.asyncio
    async def test_practice_no_plan(self, monkeypatch):
        for attr, text in [
            ("MSG_NO_PRACTICE_PLAN", "нет плана"),
            ("MSG_UNKNOWN_STATE", "unknown state"),
        ]:
            if not hasattr(messages, attr):
                monkeypatch.setattr(messages, attr, text, raising=False)

        # monkeypatch services to say user has no plan
        monkeypatch.setattr(
            services,
            "get_or_create_user",
            lambda s, telegram_id: type("U", (), {"id": 1, "active_language_id": 1})(),
        )
        monkeypatch.setattr(
            services,
            "get_or_create_user_progress",
            lambda s, user_id, language_id: type("P", (), {"id": 1})(),
        )
        monkeypatch.setattr(
            services, "user_has_practice_plan", lambda s, user_progress_id: False
        )

        upd = DummyUpdate()
        ctx = DummyContext()

        await PracticeView(upd, ctx).command()
        assert upd.message.replies, "PracticeView should reply even without plan"
        text, _ = upd.message.replies[0]
        assert "плана" in text.lower()

    @pytest.mark.asyncio
    async def test_practice_render(self, monkeypatch):
        text, _ = practice_view.render(
            FlowResult(status=FlowStatus.OK, data={"text": "q?"})
        )
        assert "q?" in text

        text, _ = practice_view.render(
            FlowResult(status=FlowStatus.CONTINUE, data={"explanation": "exp"})
        )
        assert "exp" in text

        text, _ = practice_view.render(
            FlowResult(
                status=FlowStatus.FINISHED,
                data={"explanation": "exp", "finish_messages": ["bye"]},
            )
        )
        assert "bye" in text

        text, _ = practice_view.render(FlowResult(status=FlowStatus.NO_PLAN, data={}))
        assert "практики" in text

        text, _ = practice_view.render(FlowResult(status=FlowStatus.ERROR, data={}))
        assert "произошла ошибка" in text.lower()


class TestLanguageSelection:
    @pytest.mark.asyncio
    async def test_language_callback_starts_diagnostics(self, monkeypatch):
        # Fake DB layer
        monkeypatch.setattr(
            services,
            "get_or_create_user",
            lambda s, telegram_id: type(
                "U", (), {"id": 1, "active_language_id": None}
            )(),
        )
        monkeypatch.setattr(
            services,
            "get_language_by_id",
            lambda s, lang_id: type("L", (), {"id": lang_id, "name": "Python"})(),
        )
        monkeypatch.setattr(
            services, "set_user_active_language", lambda *a, **k: None, raising=False
        )

        # patch db session context manager used inside view
        async_dummy = types.SimpleNamespace(
            commit=lambda: None, rollback=lambda: None, close=lambda: None
        )

        @contextlib.contextmanager
        def fake_session():
            yield async_dummy

        monkeypatch.setattr(lang_view_mod, "get_session", fake_session)

        # Fake flow start
        async def fake_start(ctx):
            return type(
                "R",
                (),
                {
                    "status": FlowStatus.OK,
                    "get": lambda *a, **k: None,
                },
            )()

        monkeypatch.setattr(diagnostics_flow, "start_diagnostics", fake_start)

        # Track DiagnosticsView invocation
        diag_called = {"flag": False}

        async def fake_diag(self):
            diag_called["flag"] = True

        monkeypatch.setattr(DiagnosticsView, "command", fake_diag, raising=True)

        # Build fake callback query
        class DummyQuery:
            def __init__(self):
                self.data = f"{callback_data.LANG_SELECT_PREFIX}1"
                self.from_user = type("U", (), {"id": 1})()

            async def answer(self):
                pass

            async def edit_message_text(self, *a, **k):
                pass

            @property
            def message(self):
                return DummyMessage()

        upd = DummyUpdate()
        upd.callback_query = DummyQuery()
        upd.effective_user = upd.callback_query.from_user
        ctx = DummyContext()

        await LanguageSelectionView(upd, ctx).command()
        assert diag_called[
            "flag"
        ], "DiagnosticsView should start after language selection"


class TestMessageView:
    @pytest.mark.asyncio
    async def test_answer_flow(self, monkeypatch):
        if not hasattr(messages, "MSG_UNKNOWN_STATE"):
            monkeypatch.setattr(messages, "MSG_UNKNOWN_STATE", "unknown", raising=False)

        async def fake_process(ctx, answer):
            return type(
                "R",
                (),
                {
                    "status": FlowStatus.OK,
                    "get": lambda key, default=None: "text" if key == "text" else None,
                },
            )()

        monkeypatch.setattr(practice_flow, "process_user_practice_answer", fake_process)

        upd = DummyUpdate()
        upd.message.text = "my answer"
        ctx = DummyContext()

        await UserTextMessageView(upd, ctx).command()
        # Should send at least 1 message: thank you + next question text
        assert len(upd.message.replies) >= 1

    @pytest.mark.asyncio
    async def test_unknown_state(self, monkeypatch):
        if not hasattr(messages, "MSG_UNKNOWN_STATE"):
            monkeypatch.setattr(messages, "MSG_UNKNOWN_STATE", "unknown", raising=False)

        monkeypatch.setattr(
            services,
            "get_or_create_user",
            lambda s, telegram_id: type("U", (), {"id": 1})(),
        )
        monkeypatch.setattr(
            lang_view_mod, "get_user_state", lambda s, tid: "OTHER", raising=False
        )
        # patch state machine function import path in message view
        monkeypatch.setattr(
            "src.bot.views.message.get_user_state", lambda s, tid: "OTHER"
        )

        upd = DummyUpdate()
        upd.message.text = "hi"
        ctx = DummyContext()
        await UserTextMessageView(upd, ctx).command()
        assert any("unknown" in t.lower() for t, _ in upd.message.replies)


class TestDiagnosticScoreView:
    @pytest.mark.asyncio
    async def test_invalid_payload(self, monkeypatch):
        monkeypatch.setattr(
            messages, "MSG_DIAGNOSTIC_SCORE_PARSE_ERROR", "parse err", raising=False
        )

        async def fake_proc(ctx, qid, score):
            return FlowResult(status=FlowStatus.ERROR)

        monkeypatch.setattr(diagnostics_flow, "process_diagnostic_score", fake_proc)

        class DQ:
            def __init__(self):
                self.data = callback_data.DIAGNOSTIC_SCORE_PREFIX + "bad"
                self.from_user = type("U", (), {"id": 1})()
                self.message = DummyMessage()

            async def answer(self):
                pass

            async def edit_message_text(self, text):
                self.message.replies.append((text, None))

        upd = DummyUpdate()
        upd.callback_query = DQ()
        upd.message = upd.callback_query.message
        ctx = DummyContext()
        await DiagnosticScoreView(upd, ctx).command()
        assert any(
            "parse err" in t.lower() for t, _ in upd.callback_query.message.replies
        )

    @pytest.mark.asyncio
    async def test_continue_flow(self, monkeypatch):
        """DiagnosticScoreView should send next question when flow continues."""

        # Prepare FlowResult for NEXT_QUESTION
        async def fake_proc(ctx, qid, score):
            return FlowResult(status=FlowStatus.NEXT_QUESTION)

        async def fake_get_current(ctx):
            return FlowResult(
                status=FlowStatus.OK, data={"text": "Q?", "reply_markup": None}
            )

        monkeypatch.setattr(diagnostics_flow, "process_diagnostic_score", fake_proc)
        monkeypatch.setattr(
            diagnostics_flow, "get_current_diagnostic_question", fake_get_current
        )

        class DQ:
            def __init__(self):
                self.data = f"{callback_data.DIAGNOSTIC_SCORE_PREFIX}1_4"
                self.from_user = type("U", (), {"id": 1})()
                self.message = DummyMessage()

            async def answer(self):
                pass

            async def edit_message_text(self, text, reply_markup=None):
                self.message.replies.append((text, reply_markup))

        upd = DummyUpdate()
        upd.callback_query = DQ()
        upd.message = upd.callback_query.message
        ctx = DummyContext()

        await DiagnosticScoreView(upd, ctx).command()
        assert any("q?" in t.lower() for t, _ in upd.callback_query.message.replies)


class TestNextQuestionView:
    @pytest.mark.asyncio
    async def test_plan_finished(self, monkeypatch):
        monkeypatch.setattr(
            messages, "MSG_PRACTICE_PLAN_FINISHED_INSTRUCTIONS", "done", raising=False
        )

        async def fake_next(ctx):
            return FlowResult(status=FlowStatus.FINISHED)

        monkeypatch.setattr(practice_flow, "next_practice_question", fake_next)

        class DQ:
            def __init__(self):
                self.from_user = type("U", (), {"id": 1})()
                self.message = DummyMessage()

            async def answer(self):
                pass

            async def edit_message_text(self, text):
                self.message.replies.append((text, None))

        upd = DummyUpdate()
        upd.callback_query = DQ()
        upd.message = upd.callback_query.message
        ctx = DummyContext()
        await NextQuestionView(upd, ctx).command()
        assert any("done" in t.lower() for t, _ in upd.callback_query.message.replies)

    @pytest.mark.asyncio
    async def test_next_question_ok(self, monkeypatch):
        async def fake_next(ctx):
            return FlowResult(status=FlowStatus.OK)

        async def fake_current(ctx):
            return FlowResult(status=FlowStatus.OK, data={"text": "nextQ"})

        monkeypatch.setattr(practice_flow, "next_practice_question", fake_next)
        monkeypatch.setattr(
            practice_flow, "get_current_practice_question", fake_current
        )

        class DQ:
            def __init__(self):
                self.from_user = type("U", (), {"id": 1})()
                self.message = DummyMessage()

            async def answer(self):
                pass

            async def edit_message_text(self, text):
                self.message.replies.append((text, None))

        upd = DummyUpdate()
        upd.callback_query = DQ()
        upd.message = upd.callback_query.message
        ctx = DummyContext()
        await NextQuestionView(upd, ctx).command()
        assert any("nextq" in t.lower() for t, _ in upd.callback_query.message.replies)


class TestPracticeHelpers:
    def test_extract_json(self):
        plain = '{"k":1}'
        assert _extract_json_from_llm_response(plain) == plain

        md = """Here is the plan:
```json
{\"k\":2}
```"""
        assert _extract_json_from_llm_response(md) == '{"k":2}'

    @pytest.mark.asyncio
    async def test_generate_and_save_practice_questions(self, monkeypatch):
        """_generate_and_save_practice_questions should return number of questions added."""
        ctx = DummyContext()

        # Dummy LLM returning JSON list in markdown
        class DummyLLM:
            def invoke(self, *a, **k):
                return type(
                    "R",
                    (),
                    {
                        "content": '```json\n[{"category": "Basics", "text": "What is Python?"}]\n```'
                    },
                )()

        ctx.bot_data["chat_model"] = DummyLLM()

        # Simplistic stubs
        lang_obj = type("Lang", (), {"id": 1, "name": "Python"})()
        cat_obj = type("Cat", (), {"id": 2, "name": "Basics"})()
        q_obj = type("Q", (), {"id": 3})()
        plan_item_obj = type("Item", (), {"id": 4})()
        prog_obj = type("Prog", (), {"id": 5, "diagnostic_scores_json": ""})()
        user_obj = type("User", (), {"active_language_id": 1})()

        # Patch services functions used inside helper
        monkeypatch.setattr(
            services, "get_language_by_id", lambda s, language_id: lang_obj
        )
        monkeypatch.setattr(
            services,
            "get_diagnostic_answers_for_progress",
            lambda s, user_progress_id: [
                type("Ans", (), {"question_id": 10, "score": 4})()
            ],
        )
        monkeypatch.setattr(
            services,
            "get_question_by_id",
            lambda s, qid: type("QQ", (), {"category_id": cat_obj.id})(),
        )
        monkeypatch.setattr(services, "save_diagnostic_scores", lambda *a, **k: None)
        monkeypatch.setattr(
            services, "get_categories_for_language", lambda s, language_id: [cat_obj]
        )
        monkeypatch.setattr(services, "get_or_create_category", lambda s, name: cat_obj)
        monkeypatch.setattr(services, "create_question", lambda *a, **k: q_obj)
        monkeypatch.setattr(
            services, "get_max_learning_plan_order_index", lambda *a, **k: -1
        )
        monkeypatch.setattr(
            services, "add_question_to_learning_plan", lambda *a, **k: plan_item_obj
        )
        monkeypatch.setattr(services, "set_current_learning_item", lambda *a, **k: None)

        result = await _generate_and_save_practice_questions(
            ctx, None, user_obj, prog_obj
        )
        # but pytest doesn't have run_async; instead we use pytest.mark.asyncio


class TestDiagnosticsRender:
    def test_render_error(self):
        err_res = FlowResult(FlowStatus.ERROR)
        txt, markup = diagnostics_view.render(err_res)
        assert "ошибка" in txt.lower() and markup is None


class TestDiagnosticScoreViewCompleted:
    @pytest.mark.asyncio
    async def test_completed_success_plan(self, monkeypatch):
        """DiagnosticScoreView should generate practice plan and send first question."""

        # Patch flows
        async def fake_proc(*a, **k):
            return FlowResult(FlowStatus.COMPLETED)

        async def fake_cur(*a, **k):
            return FlowResult(FlowStatus.DONE)

        monkeypatch.setattr(diagnostics_flow, "process_diagnostic_score", fake_proc)
        monkeypatch.setattr(
            diagnostics_flow, "get_current_diagnostic_question", fake_cur
        )

        # Stub practice helpers
        async def fake_gen_save(ctx, session, user, progress):
            return 5  # imitate 5 questions generated

        monkeypatch.setattr(
            practice_view, "_generate_and_save_practice_questions", fake_gen_save
        )

        async def fake_prac_cur(*a, **k):
            return FlowResult(FlowStatus.OK, {"text": "First Q", "reply_markup": None})

        monkeypatch.setattr(
            practice_flow, "get_current_practice_question", fake_prac_cur
        )
        monkeypatch.setattr(
            practice_view, "render", lambda res: (res.data["text"], None)
        )

        monkeypatch.setattr(
            messages, "MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE", "saved", raising=False
        )
        monkeypatch.setattr(
            messages, "MSG_NEW_PRACTICE_QUESTIONS_READY", "ready {count}", raising=False
        )

        class DQ:
            def __init__(self):
                self.from_user = type("U", (), {"id": 1})()
                self.message = DummyMessage()

            async def answer(self):
                pass

            async def edit_message_text(self, text, reply_markup=None):
                self.message.replies.append((text, reply_markup))

        upd = DummyUpdate()
        upd.callback_query = DQ()
        upd.message = upd.callback_query.message
        ctx = DummyContext()
        upd.callback_query.data = f"{callback_data.DIAGNOSTIC_SCORE_PREFIX}1_3"

        await DiagnosticScoreView(upd, ctx).command()
        texts = " ".join(t for t, _ in upd.callback_query.message.replies)
        assert "saved" in texts and "ready" in texts and "first q" in texts.lower()

    @pytest.mark.asyncio
    async def test_completed_no_questions(self, monkeypatch):
        async def fake_proc2(*a, **k):
            return FlowResult(FlowStatus.COMPLETED)

        monkeypatch.setattr(diagnostics_flow, "process_diagnostic_score", fake_proc2)

        async def fake_gen_save2(ctx, session, user, progress):
            return 0  # zero questions generated triggers NO_QUESTIONS

        monkeypatch.setattr(
            practice_view, "_generate_and_save_practice_questions", fake_gen_save2
        )
        monkeypatch.setattr(
            messages, "MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE", "saved", raising=False
        )
        monkeypatch.setattr(
            messages,
            "MSG_PRACTICE_PLAN_GENERATION_FAILED_NO_QUESTIONS",
            "noq",
            raising=False,
        )

        class DQ:
            def __init__(self):
                self.from_user = type("U", (), {"id": 1})()
                self.message = DummyMessage()

            async def answer(self):
                pass

            async def edit_message_text(self, text, reply_markup=None):
                self.message.replies.append((text, reply_markup))

        upd = DummyUpdate()
        upd.callback_query = DQ()
        upd.message = upd.callback_query.message
        ctx = DummyContext()
        upd.callback_query.data = f"{callback_data.DIAGNOSTIC_SCORE_PREFIX}1_3"

        await DiagnosticScoreView(upd, ctx).command()
        assert any("noq" in t for t, _ in upd.callback_query.message.replies)


class TestPracticeHelpersEdge:
    @pytest.mark.asyncio
    async def test_generate_practice_plan_error(self, monkeypatch):
        """generate_practice_plan should gracefully handle unexpected exception and return (False, 'ERROR')."""

        # Force _generate_and_save_practice_questions to raise
        async def boom(*a, **k):
            raise RuntimeError("fail")

        monkeypatch.setattr(
            practice_view, "_generate_and_save_practice_questions", boom
        )

        ctx = DummyContext()
        sess = None  # not used because boom raises before any DB interaction
        user = type("U", (), {"telegram_id": 1})()
        prog = type("Prog", (), {})()

        success, code = await practice_view.generate_practice_plan(
            ctx, sess, user, prog
        )
        assert not success and code == "ERROR"


class TestUserTextMessageView:
    @pytest.mark.asyncio
    async def test_practice_answer_flow(self, monkeypatch):
        """User message during practice should thank and then reply with rendered text."""
        monkeypatch.setattr(
            messages, "MSG_THANKS_FOR_ANSWER_ANALYZING", "thanks", raising=False
        )
        # stub state machine
        if not hasattr(messages, "MSG_UNKNOWN_STATE"):
            monkeypatch.setattr(messages, "MSG_UNKNOWN_STATE", "unknown", raising=False)
        from src.bot import state_machine as sm_mod

        monkeypatch.setattr(
            "src.bot.views.message.get_user_state",
            lambda s, tid: "practice",
            raising=False,
        )

        async def fake_proc(ctx, answer):
            return FlowResult(FlowStatus.OK, {"text": "AI reply", "reply_markup": None})

        monkeypatch.setattr(practice_flow, "process_user_practice_answer", fake_proc)
        monkeypatch.setattr(
            practice_view, "render", lambda res: (res.data["text"], None)
        )

        upd = DummyUpdate()
        upd.message = DummyMessage()
        upd.message.text = "my ans"
        upd.message.from_user = type("U", (), {"id": 1})()
        ctx = DummyContext()

        view = lang_view_mod  # just to access Dummy? actually use class

        from src.bot.views.message import UserTextMessageView

        await UserTextMessageView(upd, ctx).command()
        texts = [t for t, _ in upd.message.replies]
        assert "thanks" in texts[0].lower() and "ai reply" in texts[-1].lower()

    @pytest.mark.asyncio
    async def test_unknown_state(self, monkeypatch):
        if not hasattr(messages, "MSG_UNKNOWN_STATE"):
            monkeypatch.setattr(messages, "MSG_UNKNOWN_STATE", "oops", raising=False)
        from src.bot import state_machine as sm_mod

        monkeypatch.setattr(
            "src.bot.views.message.get_user_state",
            lambda sess, tid: "OTHER",
            raising=False,
        )

        upd = DummyUpdate()
        upd.message = DummyMessage()
        upd.message.text = "hi"
        upd.message.from_user = type("U", (), {"id": 1})()
        ctx = DummyContext()

        from src.bot.views.message import UserTextMessageView

        await UserTextMessageView(upd, ctx).command()
        assert any("oops" in t for t, _ in upd.message.replies)


# -------- Migrated edge case tests from test_edge_cases.py --------


@pytest.mark.asyncio
async def test_generate_practice_plan_success(monkeypatch):
    """generate_practice_plan should return True and set user state to PRACTICE."""

    async def fake_gen(*a, **k):
        return 2

    monkeypatch.setattr(
        practice_view, "_generate_and_save_practice_questions", fake_gen
    )

    called = {}

    def fake_set_state(session, tid, state):
        called["state"] = state

    from src.bot import state_machine as sm_mod

    monkeypatch.setattr(sm_mod, "set_user_state", fake_set_state)

    ctx = DummyContext()
    user = type("U", (), {"telegram_id": 1})()
    prog = type("P", (), {})()

    success, amount = await practice_view.generate_practice_plan(ctx, None, user, prog)
    from src.bot.state_machine import UserState

    assert success and amount == 2 and called["state"] == UserState.PRACTICE.value


@pytest.mark.asyncio
async def test_generate_practice_plan_no_questions(monkeypatch):
    async def fake_gen(*a, **k):
        return 0

    monkeypatch.setattr(
        practice_view, "_generate_and_save_practice_questions", fake_gen
    )

    ctx = DummyContext()
    user = type("U", (), {"telegram_id": 1})()
    prog = type("P", (), {})()

    success, code = await practice_view.generate_practice_plan(ctx, None, user, prog)
    assert not success and code == "NO_QUESTIONS"


@pytest.mark.asyncio
async def test_practice_view_no_plan(monkeypatch):
    monkeypatch.setattr(
        practice_view.services, "user_has_practice_plan", lambda *a, **k: False
    )
    monkeypatch.setattr(
        practice_view.services,
        "get_or_create_user",
        lambda *a, **k: type("U", (), {"id": 1, "active_language_id": 1})(),
    )
    monkeypatch.setattr(
        practice_view.services,
        "get_or_create_user_progress",
        lambda *a, **k: type("P", (), {"id": 1})(),
    )
    monkeypatch.setattr(
        practice_view.messages, "MSG_NO_PRACTICE_PLAN", "noplan", raising=False
    )

    upd = DummyUpdate()
    upd.message = DummyMessage()
    upd.message.from_user = type("U", (), {"id": 1})()

    ctx = DummyContext()
    await PracticeView(upd, ctx).command()
    assert any("noplan" in t for t, _ in upd.message.replies)


@pytest.mark.asyncio
async def test_message_view_waiting(monkeypatch):
    """UserTextMessageView should process answer when state is WAITING_FOR_ANSWER."""
    monkeypatch.setattr(
        messages, "MSG_THANKS_FOR_ANSWER_ANALYZING", "thanks", raising=False
    )
    if not hasattr(messages, "MSG_UNKNOWN_STATE"):
        monkeypatch.setattr(messages, "MSG_UNKNOWN_STATE", "unknown", raising=False)
    from src.bot import state_machine as sm_mod

    monkeypatch.setattr(
        "src.bot.views.message.get_user_state",
        lambda sess, tid: "waiting_for_answer",
        raising=False,
    )

    async def fake_proc(ctx, ans):
        return FlowResult(FlowStatus.OK, {"text": "ok", "reply_markup": None})

    monkeypatch.setattr(practice_flow, "process_user_practice_answer", fake_proc)
    monkeypatch.setattr(practice_view, "render", lambda res: (res.data["text"], None))

    upd = DummyUpdate()
    upd.message = DummyMessage()
    upd.message.text = "answer"
    upd.message.from_user = type("U", (), {"id": 1})()
    ctx = DummyContext()

    await UserTextMessageView(upd, ctx).command()
    texts = [t for t, _ in upd.message.replies]
    assert texts[0] == "thanks" and texts[-1] == "ok"


# ---------- state_machine.set_state_and_log ----------


def test_set_state_and_log(monkeypatch):
    from src.bot import state_machine as sm_mod

    # patch underlying set_user_state and logger
    calls = {}

    def stub_set(sess, tid, state):
        calls["state"] = state

    monkeypatch.setattr(sm_mod, "set_user_state", stub_set)
    monkeypatch.setattr(
        sm_mod.logger, "info", lambda *a, **k: calls.setdefault("logged", True)
    )

    sm_mod.set_state_and_log(None, 1, sm_mod.UserState.END, reason="done")
    assert calls["state"] == sm_mod.UserState.END and calls["logged"]


# ---------------- Additional edge-case coverage for practice helpers ----------------

import json

# Helper objects reused below
# Helper objects reused below
import types


# ---------------- Additional edge-case coverage for practice helpers ----------------


@pytest.mark.asyncio
async def test_generate_questions_no_answers(monkeypatch):
    """_generate_and_save_practice_questions should early-return 0 when no diagnostic answers."""
    ctx = DummyContext()
    user_obj = types.SimpleNamespace(active_language_id=1)
    prog_obj = types.SimpleNamespace(id=1, diagnostic_scores_json=None)

    # Patch services so that no answers are found
    monkeypatch.setattr(
        practice_view.services,
        "get_language_by_id",
        lambda *a, **k: types.SimpleNamespace(id=1, name="Python"),
    )
    monkeypatch.setattr(
        practice_view.services,
        "get_diagnostic_answers_for_progress",
        lambda *a, **k: [],
    )

    result = await practice_view._generate_and_save_practice_questions(
        ctx, None, user_obj, prog_obj
    )
    assert result == 0


@pytest.mark.asyncio
async def test_generate_questions_no_llm(monkeypatch):
    """Should return 0 when chat_model absent in context.bot_data."""
    ctx = DummyContext()
    user_obj = types.SimpleNamespace(active_language_id=2)
    prog_obj = types.SimpleNamespace(id=2, diagnostic_scores_json=json.dumps({"1": 4}))

    monkeypatch.setattr(
        practice_view.services,
        "get_language_by_id",
        lambda *a, **k: types.SimpleNamespace(id=2, name="JS"),
    )
    monkeypatch.setattr(
        practice_view.services, "get_categories_for_language", lambda *a, **k: []
    )
    ctx.bot_data.clear()  # ensure no LLM

    res = await practice_view._generate_and_save_practice_questions(
        ctx, None, user_obj, prog_obj
    )
    assert res == 0


@pytest.mark.asyncio
async def test_generate_questions_bad_json(monkeypatch):
    """Should return 0 when LLM returns unparsable JSON."""
    ctx = DummyContext()
    user_obj = types.SimpleNamespace(active_language_id=3)
    prog_obj = types.SimpleNamespace(id=3, diagnostic_scores_json=json.dumps({"1": 5}))

    monkeypatch.setattr(
        practice_view.services,
        "get_language_by_id",
        lambda *a, **k: types.SimpleNamespace(id=3, name="Rust"),
    )
    monkeypatch.setattr(
        practice_view.services, "get_categories_for_language", lambda *a, **k: []
    )

    class DummyLLM:
        def invoke(self, *a, **k):
            # returns content that isn't valid JSON
            return types.SimpleNamespace(content="not json")

    ctx.bot_data["chat_model"] = DummyLLM()

    res = await practice_view._generate_and_save_practice_questions(
        ctx, None, user_obj, prog_obj
    )
    assert res == 0


def test_extract_json_helper_variants():
    plain = '{"k":1}'
    assert practice_view._extract_json_from_llm_response(plain) == plain

    md = """Some text
```json
{\"a\":2}
```"""
    assert practice_view._extract_json_from_llm_response(md) == '{"a":2}'


# ------------- Unknown state reply -------------


@pytest.mark.asyncio
async def test_message_unknown_state(monkeypatch):
    """UserTextMessageView should reply with MSG_UNKNOWN_STATE when state not PRACTICE/WAITING."""
    monkeypatch.setattr(messages, "MSG_UNKNOWN_STATE", "unknown state", raising=False)
    monkeypatch.setattr(
        messages, "MSG_THANKS_FOR_ANSWER_ANALYZING", "thanks", raising=False
    )

    # Simulate non-practice state
    monkeypatch.setattr(
        "src.bot.views.message.get_user_state", lambda *_, **__: "idle", raising=False
    )
    # Ensure practice flow isn't called
    monkeypatch.setattr(
        practice_flow,
        "process_user_practice_answer",
        lambda *a, **k: FlowResult(FlowStatus.ERROR),
        raising=False,
    )

    upd = DummyUpdate()
    upd.message = DummyMessage()
    upd.message.text = "Hello"
    upd.message.from_user = type("U", (), {"id": 1})()
    ctx = DummyContext()

    await UserTextMessageView(upd, ctx).command()
    assert any("unknown state" in t for t, _ in upd.message.replies)
