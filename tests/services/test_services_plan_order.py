from src.db import services


def test_order_index_increment(session):
    lang = services.get_or_create_language(session, name="C#", slug="csharp")
    cat = services.get_or_create_category(session, name="LINQ")
    q1 = services.create_question(session, text="q1", category_id=cat.id, language_id=lang.id)
    q2 = services.create_question(session, text="q2", category_id=cat.id, language_id=lang.id)

    user = services.get_or_create_user(session, telegram_id=51)
    progress = services.get_or_create_user_progress(session, user.id, lang.id)

    max_idx = services.get_max_learning_plan_order_index(session, progress.id)
    assert max_idx == -1

    it1 = services.add_question_to_learning_plan(session, progress.id, q1.id, order_index=0)
    it2 = services.add_question_to_learning_plan(session, progress.id, q2.id, order_index=1)

    assert it2.order_index == it1.order_index + 1
