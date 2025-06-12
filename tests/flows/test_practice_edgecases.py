import pytest
from src.bot.flows import practice
from src.db import services


@pytest.mark.asyncio
async def test_no_plan(session, test_context):
    user = services.get_or_create_user(session, telegram_id=77)
    test_context.user_data["telegram_id"] = user.telegram_id

    res = await practice.get_current_practice_question(test_context)
    assert res.status.name == "NO_PLAN"
    res = await practice.get_current_practice_question(test_context)
    assert res.status.name == "NO_PLAN"
