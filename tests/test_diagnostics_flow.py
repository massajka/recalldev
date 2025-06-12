import pytest
from src.bot.flows import diagnostics as diag
from src.db import services


@pytest.mark.asyncio
async def test_full_diagnostics_flow(session, test_context, sample_questions):
    """Happy path: start → iterate questions → complete."""

    # Arrange: use sample questions
    data = sample_questions  # fixture
    q1, q2 = data.diag_q, data.diag_q2
    test_context.user_data["telegram_id"] = data.user.telegram_id

    # Act 1: start diagnostics
    start_res = await diag.start_diagnostics(test_context)
    assert start_res.status is not None  # should be OK or NO_QUESTIONS
    dq_ids = test_context.user_data["diagnostic_question_ids"]
    # Должны содержать хотя бы наши вопросы первыми в списке
    assert dq_ids[:2] == [q1.id, q2.id]

    # Act 2: get first question
    qres1 = await diag.get_current_diagnostic_question(test_context)
    assert qres1.status.name == "OK"
    assert data.diag_q.text.split("?")[0] in qres1.data["text"]

    # Act 3: answer first question
    ans1 = await diag.process_diagnostic_score(test_context, q1.id, 3)
    assert ans1.status.name in {"NEXT_QUESTION", "COMPLETED"}

    # Act 4: second question
    qres2 = await diag.get_current_diagnostic_question(test_context)
    assert data.diag_q2.text.split("?")[0] in qres2.data["text"]

    # finish
    ans2 = await diag.process_diagnostic_score(test_context, q2.id, 4)
    assert ans2.status.name == "COMPLETED"
