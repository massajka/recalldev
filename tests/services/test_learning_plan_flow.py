from src.db import services


def test_learning_plan_full_cycle(session):
    lang = services.get_or_create_language(session, "Ruby", "ruby")
    cat = services.get_or_create_category(session, "Syntax")
    q1 = services.create_question(session, "blocks?", cat.id, lang.id)
    q2 = services.create_question(session, "yield keyword?", cat.id, lang.id)

    user = services.get_or_create_user(session, 321)
    prog = services.get_or_create_user_progress(session, user.id, lang.id)

    it1 = services.add_question_to_learning_plan(session, prog.id, q1.id, 0)
    it2 = services.add_question_to_learning_plan(session, prog.id, q2.id, 1)

    # set current
    services.set_current_learning_item(session, prog.id, it1.id)
    cur = services.get_current_learning_item(session, prog.id)
    assert cur.id == it1.id

    # next pending
    nxt = services.get_next_pending_learning_item(session, prog.id, current_order_index=cur.order_index)
    assert nxt.id == it2.id

    # update status and set next current
    services.update_learning_item_status(session, it1.id, "answered")
    services.set_current_learning_item(session, prog.id, it2.id)
    assert services.get_current_learning_item(session, prog.id).id == it2.id

    # max order index helper
    assert services.get_max_learning_plan_order_index(session, prog.id) == 1

    # when no pending left returns None
    services.update_learning_item_status(session, it2.id, "answered")
    assert services.get_next_pending_learning_item(session, prog.id, cur.order_index) is None
