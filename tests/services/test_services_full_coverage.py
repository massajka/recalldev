import copy
from src.db import services

def test_services_full_coverage(session, monkeypatch):
    # 1. list_languages baseline count
    base_count = len(services.list_languages(session))

    # create new language and verify increment (line 39)
    lang = services.get_or_create_language(session, "Rust", "rust")
    assert len(services.list_languages(session)) == base_count + 1

    # 2. Category helpers covering 53,62,91,98
    assert services.get_category_by_name(session, "Memory") is None  # 53 none path
    cat = services.get_or_create_category(session, "Memory")
    # 62 path inside get_category_by_name_and_language when category exists but no question
    assert services.get_category_by_name_and_language(session, "Memory", lang.id) is None

    # add question then helper returns category (98 path)
    q = services.create_question(session, "What is ownership?", cat.id, lang.id)
    assert services.get_category_by_name_and_language(session, cat.name, lang.id) == cat

    # 3. user_has_practice_plan false & true (163,171)
    user = services.get_or_create_user(session, 1001)
    prog = services.get_or_create_user_progress(session, user.id, lang.id)
    assert services.user_has_practice_plan(session, prog.id) is False
    item = services.add_question_to_learning_plan(session, prog.id, q.id, 0)
    assert services.user_has_practice_plan(session, prog.id) is True

    # 4. get_next_pending_learning_item with default current_order_index None (258)
    assert services.get_next_pending_learning_item(session, prog.id) == item

    # 5. save_diagnostic_scores (309)
    services.save_diagnostic_scores(session, prog.id, {"score": 3})

    # 6. update_learning_item_status (347-348)
    services.update_learning_item_status(session, item.id, "answered")

    # 7. populate_initial_data warnings (423-430)
    bad_data = copy.deepcopy(services.INITIAL_DATA)
    bad_data["diagnostic_questions"] = {"rust": [{"category": "UnknownCat", "text": "bad"}]}
    monkeypatch.setattr(services, "INITIAL_DATA", bad_data, raising=False)
    services.populate_initial_data(session)

    # restore
    monkeypatch.setattr(services, "INITIAL_DATA", copy.deepcopy(services.INITIAL_DATA), raising=False)

    # 8. try_populate_initial_data languages already exist (449-452)
    services.try_populate_initial_data()
