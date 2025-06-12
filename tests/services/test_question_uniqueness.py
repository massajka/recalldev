from src.db import services


def test_add_question_uniqueness(session):
    lang = services.get_or_create_language(session, name="Dart", slug="dart")
    cat = services.get_or_create_category(session, name="BasicsD")

    q1 = services.create_question(session, text="What is Dart?", category_id=cat.id, language_id=lang.id)
    q2 = services.create_question(session, text="What is Dart?", category_id=cat.id, language_id=lang.id)

    # функция должна вернуть существующий вопрос при дублировании
    assert q1.id == q2.id
