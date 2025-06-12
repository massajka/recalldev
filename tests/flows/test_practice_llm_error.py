import pytest
from src.bot.flows import practice
from src.db import services


@pytest.mark.asyncio
async def test_llm_none(session, test_context, sample_questions):
    data = sample_questions
    progress = services.get_or_create_user_progress(session, data.user.id, data.lang.id)
    services.add_question_to_learning_plan(session, progress.id, data.q1.id, order_index=0)
    services.set_current_learning_item(session, progress.id, 1)
    test_context.user_data["telegram_id"] = data.user.telegram_id

    # bot_data chat_model intentionally None -> explanation should be ''
    test_context.bot_data.pop("chat_model", None)

    res = await practice.process_user_practice_answer(test_context, "42")
    assert res.get("explanation") == ""
