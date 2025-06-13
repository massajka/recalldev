import pytest

from src.bot.flow_result import FlowStatus
from src.bot.flows import diagnostics as diag_flow
from src.bot.flows import practice as prac_flow
from src.db import services


@pytest.mark.asyncio
async def test_start_diagnostics_no_language(session, test_context):
    """If user has not selected a language the flow should respond NO_LANGUAGE."""
    user = services.get_or_create_user(session, telegram_id=501)
    # user.active_language_id is None by default
    test_context.user_data["telegram_id"] = user.telegram_id

    res = await diag_flow.start_diagnostics(test_context)
    assert res.status == FlowStatus.NO_LANGUAGE


@pytest.mark.asyncio
async def test_full_diagnostics_flow(sample_questions, test_context):
    """Walk through diagnostics: start -> next question -> completed."""
    user = sample_questions.user
    test_context.user_data["telegram_id"] = user.telegram_id

    # Start diagnostics – should return first question immediately
    first = await diag_flow.start_diagnostics(test_context)
    assert first.status == FlowStatus.OK and "text" in first.data
    # There should be at least two diagnostic questions as created in sample_questions
    q_ids = test_context.user_data["diagnostic_question_ids"]
    assert len(q_ids) >= 2

    # Answer first question with score 3
    res_next = await diag_flow.process_diagnostic_score(
        test_context, question_id=q_ids[0], score=3
    )
    # Depending on question count the flow might complete immediately
    if res_next.status == FlowStatus.NEXT_QUESTION:
        second_q = await diag_flow.get_current_diagnostic_question(test_context)
        assert second_q.status == FlowStatus.OK and "text" in second_q.data

        res_done = await diag_flow.process_diagnostic_score(
            test_context, question_id=q_ids[1], score=4
        )
        assert res_done.status == FlowStatus.COMPLETED
    else:
        assert res_next.status == FlowStatus.COMPLETED


@pytest.mark.asyncio
async def test_practice_get_current_question(sample_questions, test_context, session):
    """If practice plan exists and current item set, flow returns OK with question text."""
    user = sample_questions.user
    lang = sample_questions.lang
    q1 = sample_questions.q1

    # Create progress & learning plan
    progress = services.get_or_create_user_progress(session, user.id, lang.id)
    item = services.add_question_to_learning_plan(session, progress.id, q1.id, 0)
    services.set_current_learning_item(session, progress.id, item.id)

    test_context.user_data["telegram_id"] = user.telegram_id

    res = await prac_flow.get_current_practice_question(test_context)
    assert res.status == FlowStatus.OK
    assert q1.text in res.data["text"]


@pytest.mark.asyncio
async def test_diagnostics_auto_start(session, test_context):
    """Calling get_current_diagnostic_question without prior explicit start auto-starts and returns OK."""
    lang = services.get_or_create_language(session, "JS", "js")
    cat = services.get_or_create_category(session, "BasicsJS")
    q = services.create_question(
        session, "Что такое hoisting?", cat.id, lang.id, is_diagnostic=True
    )
    q2 = services.create_question(
        session, "Область видимости var?", cat.id, lang.id, is_diagnostic=True
    )

    user = services.get_or_create_user(session, telegram_id=999)
    services.set_user_active_language(session, user.id, lang.id)
    test_context.user_data["telegram_id"] = user.telegram_id

    res = await diag_flow.get_current_diagnostic_question(test_context)
    assert res.status == FlowStatus.OK
    assert any(
        txt in res.data["text"] for txt in (q.text.split("?")[0], q2.text.split("?")[0])
    )


@pytest.mark.asyncio
async def test_no_active_language(session, test_context):
    user = services.get_or_create_user(session, telegram_id=888)
    test_context.user_data["telegram_id"] = user.telegram_id

    res = await diag_flow.start_diagnostics(test_context)
    assert res.status == FlowStatus.NO_LANGUAGE


@pytest.mark.asyncio
async def test_no_diagnostic_questions(session, test_context):
    lang = services.get_or_create_language(session, name="Go", slug="go")
    user = services.get_or_create_user(session, telegram_id=889)
    services.set_user_active_language(session, user.id, lang.id)
    test_context.user_data["telegram_id"] = user.telegram_id

    res = await diag_flow.start_diagnostics(test_context)
    assert res.status == FlowStatus.NO_QUESTIONS


@pytest.mark.asyncio
async def test_llm_none(sample_questions, test_context, session):
    """If LLM model is absent, explanation should be empty string."""
    data = sample_questions
    progress = services.get_or_create_user_progress(session, data.user.id, data.lang.id)
    item = services.add_question_to_learning_plan(
        session, progress.id, data.q1.id, order_index=0
    )
    services.set_current_learning_item(session, progress.id, item.id)

    test_context.user_data["telegram_id"] = data.user.telegram_id
    test_context.bot_data.pop("chat_model", None)  # Ensure no model

    res = await prac_flow.process_user_practice_answer(test_context, "42")
    assert res.data["explanation"] == ""


# ---------------- Consolidated classes from separate flow test files -----------------

import pytest
from telegram import InlineKeyboardMarkup

from constants import callback_data


class TestDiagnosticFlow:
    """Grouped diagnostic flow scenarios."""

    @pytest.mark.asyncio
    async def test_full_diagnostics_happy_path(
        self, session, test_context, sample_questions
    ):
        """Formerly from tests/test_diagnostics_flow.py – end-to-end happy path."""
        data = sample_questions
        q1, q2 = data.diag_q, data.diag_q2
        test_context.user_data["telegram_id"] = data.user.telegram_id

        start_res = await diag_flow.start_diagnostics(test_context)
        assert start_res.status == FlowStatus.OK
        dq_ids = test_context.user_data["diagnostic_question_ids"]
        assert dq_ids[:2] == [q1.id, q2.id]

        qres1 = await diag_flow.get_current_diagnostic_question(test_context)
        assert qres1.status == FlowStatus.OK

        ans1 = await diag_flow.process_diagnostic_score(test_context, q1.id, 3)
        assert ans1.status in {FlowStatus.NEXT_QUESTION, FlowStatus.COMPLETED}

        qres2 = await diag_flow.get_current_diagnostic_question(test_context)
        if qres2.status == FlowStatus.OK:
            assert q2.text.split("?")[0] in qres2.data["text"]

            ans2 = await diag_flow.process_diagnostic_score(test_context, q2.id, 4)
            assert ans2.status == FlowStatus.COMPLETED
        else:
            # Flow already finished
            assert qres2.status in {FlowStatus.DONE, FlowStatus.NO_ACTIVE_QUESTION}


class TestPracticeFlow:
    """Grouped practice flow scenarios."""

    @pytest.mark.asyncio
    async def test_practice_answer_and_next(
        self, session, test_context, sample_questions
    ):
        """Former tests/test_practice_flow.py – answer current question and move next."""
        data = sample_questions

        progress = services.get_or_create_user_progress(
            session, data.user.id, data.lang.id
        )
        item1 = services.add_question_to_learning_plan(
            session, progress.id, data.q1.id, order_index=0
        )
        services.add_question_to_learning_plan(
            session, progress.id, data.q2.id, order_index=1
        )
        services.set_current_learning_item(session, progress.id, item1.id)

        test_context.user_data["telegram_id"] = data.user.telegram_id

        qres = await prac_flow.get_current_practice_question(test_context)
        assert qres.status == FlowStatus.OK
        assert "What is Python?" in qres.data["text"]

        ans_res = await prac_flow.process_user_practice_answer(
            test_context, "My answer"
        )
        assert ans_res.status == FlowStatus.CONTINUE
        assert "FAKE_EXPLANATION" in ans_res.data["explanation"]
        assert isinstance(ans_res.data["reply_markup"], InlineKeyboardMarkup)

        test_context.user_data[callback_data.ACTION_NEXT_QUESTION] = True
        next_res = await prac_flow.next_practice_question(test_context)
        assert next_res.status in {FlowStatus.OK, FlowStatus.FINISHED}


# -------- Edge cases for flows --------


@pytest.mark.asyncio
async def test_diagnostics_get_current_error(monkeypatch):
    """If question not found, diagnostics flow returns ERROR."""

    def fake_get_question(*a, **k):
        return None

    monkeypatch.setattr(diag_flow.services, "get_question_by_id", fake_get_question)

    from tests.test_views import DummyContext

    ctx = DummyContext()
    ctx.user_data.update(
        {
            "telegram_id": 1,
            "active_progress_id": 1,
            "diagnostic_question_ids": [99],
            "diagnostic_current_index": 0,
        }
    )
    res = await diag_flow.get_current_diagnostic_question(ctx)
    assert res.status == FlowStatus.ERROR


# note: similar scenario tested elsewhere; avoid duplicate function name


@pytest.mark.asyncio
async def test_practice_get_current_no_plan(monkeypatch):
    monkeypatch.setattr(
        prac_flow.services, "user_has_practice_plan", lambda *a, **k: False
    )
    monkeypatch.setattr(
        prac_flow.services, "get_current_learning_item", lambda *a, **k: None
    )
    monkeypatch.setattr(
        prac_flow.services,
        "get_or_create_user",
        lambda *a, **k: type("U", (), {"id": 1, "active_language_id": 1})(),
    )
    monkeypatch.setattr(
        prac_flow.services,
        "get_or_create_user_progress",
        lambda *a, **k: type("P", (), {"id": 1})(),
    )

    from tests.test_views import DummyContext

    ctx = DummyContext()
    ctx.user_data["telegram_id"] = 1
    res = await prac_flow.get_current_practice_question(ctx)
    assert res.status == FlowStatus.NO_PLAN


@pytest.mark.asyncio
async def test_practice_next_finished(monkeypatch):
    monkeypatch.setattr(
        prac_flow.services, "get_next_pending_learning_item", lambda *a, **k: None
    )
    monkeypatch.setattr(
        prac_flow.services,
        "get_or_create_user",
        lambda *a, **k: type("U", (), {"id": 1, "active_language_id": 1})(),
    )
    monkeypatch.setattr(
        prac_flow.services,
        "get_or_create_user_progress",
        lambda *a, **k: type("P", (), {"id": 1})(),
    )

    from tests.test_views import DummyContext

    ctx = DummyContext()
    ctx.user_data["telegram_id"] = 1
    res = await prac_flow.next_practice_question(ctx)
    assert res.status == FlowStatus.FINISHED


@pytest.mark.asyncio
async def test_diagnostics_process_no_active_question(monkeypatch):
    """process_diagnostic_score without active_progress_id should return NO_ACTIVE_QUESTION."""
    from tests.test_views import DummyContext

    ctx = DummyContext()
    ctx.user_data["telegram_id"] = 1

    res = await diag_flow.process_diagnostic_score(ctx, question_id=1, score=3)
    assert res.status == FlowStatus.NO_ACTIVE_QUESTION
