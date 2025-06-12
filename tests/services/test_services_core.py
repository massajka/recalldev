from src.db import services


def test_learning_plan_lifecycle(session):
    lang = services.get_or_create_language(session, name="JS", slug="js")
    cat = services.get_or_create_category(session, name="Async")
    q = services.create_question(session, text="Explain Promise", category_id=cat.id, language_id=lang.id)

    user = services.get_or_create_user(session, telegram_id=42)
    services.set_user_active_language(session, user.id, lang.id)

    progress = services.get_or_create_user_progress(session, user.id, lang.id)
    item = services.add_question_to_learning_plan(session, progress.id, q.id, order_index=0)
    assert services.user_has_practice_plan(session, progress.id)

    # current item should be None until set
    assert services.get_current_learning_item(session, progress.id) is None
    services.set_current_learning_item(session, progress.id, item.id)
    assert services.get_current_learning_item(session, progress.id) is not None
