import pytest
from src.bot.flows import diagnostics as diag
from src.db import services


@pytest.mark.asyncio
async def test_diagnostics_auto_start(session, test_context):
    """Calling get_current_diagnostic_question without prior start should auto-start without ERROR."""
    # Arrange minimal data
    lang = services.get_or_create_language(session, "JS", "js")
    cat = services.get_or_create_category(session, "BasicsJS")
    q = services.create_question(session, "Что такое hoisting?", cat.id, lang.id, is_diagnostic=True)

    user = services.get_or_create_user(session, telegram_id=999)
    services.set_user_active_language(session, user.id, lang.id)
    test_context.user_data["telegram_id"] = user.telegram_id

    # Act: directly asking for current question triggers auto-start inside flow
    res = await diag.start_diagnostics(test_context)

    # Assert
    assert res.status.name == "OK"
    assert str(q.text.split("?")[0]) in res.data["text"]
