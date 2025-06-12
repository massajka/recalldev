import pytest
from src.bot.flows import practice
from src.db import services
from constants import callback_data
from telegram import InlineKeyboardMarkup

@pytest.mark.asyncio
async def test_practice_answer_and_next(session, test_context, sample_questions):
    data = sample_questions

    # Prepare learning plan
    progress = services.get_or_create_user_progress(session, data.user.id, data.lang.id)
    item1 = services.add_question_to_learning_plan(session, progress.id, data.q1.id, order_index=0)
    services.add_question_to_learning_plan(session, progress.id, data.q2.id, order_index=1)
    services.set_current_learning_item(session, progress.id, item1.id)

    test_context.user_data.update({"telegram_id": data.user.telegram_id})

    # current question
    qres = await practice.get_current_practice_question(test_context)
    assert qres.status.name == "OK"
    assert "What is Python?" in qres.data["text"]

    # answer
    ans_res = await practice.process_user_practice_answer(test_context, "My answer")
    assert ans_res.status.name == "CONTINUE"
    assert "FAKE_EXPLANATION" in ans_res.data["explanation"]
    assert isinstance(ans_res.data["reply_markup"], InlineKeyboardMarkup)

    # next
    test_context.user_data[callback_data.ACTION_NEXT_QUESTION] = True  # simulation
    next_res = await practice.next_practice_question(test_context)
    assert next_res.status.name in {"OK", "FINISHED"}
