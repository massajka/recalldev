from src.db import services


def test_getters_by_id(session):
    lang = services.get_or_create_language(session, name="Swift", slug="swift")
    cat = services.get_or_create_category(session, name="Memory")
    q = services.create_question(session, text="ARC?", category_id=cat.id, language_id=lang.id)

    # language
    assert services.get_language_by_id(session, lang.id).slug == "swift"

    # question
    assert services.get_question_by_id(session, q.id).text == "ARC?"

    # category via helper
    found_cat = services.get_category_by_name_and_language(session, cat.name, lang.id)
    assert found_cat.id == cat.id
