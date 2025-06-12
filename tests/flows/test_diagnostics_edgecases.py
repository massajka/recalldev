import pytest
from src.bot.flows import diagnostics as diag
from src.db import services


@pytest.mark.asyncio
async def test_no_active_language(session, test_context):
    # user w/o active language
    user = services.get_or_create_user(session, telegram_id=888)
    test_context.user_data["telegram_id"] = user.telegram_id

    res = await diag.start_diagnostics(test_context)
    assert res.status.name == "NO_LANGUAGE"


@pytest.mark.asyncio
async def test_no_diagnostic_questions(session, test_context):
    # user with language but empty question set
    lang = services.get_or_create_language(session, name="Go", slug="go")
    user = services.get_or_create_user(session, telegram_id=889)
    services.set_user_active_language(session, user.id, lang.id)
    test_context.user_data["telegram_id"] = user.telegram_id

    res = await diag.start_diagnostics(test_context)
    assert res.status.name == "NO_QUESTIONS"
