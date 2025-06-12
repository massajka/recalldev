from src.db import services
from sqlmodel import select


def test_category_helpers(session):
    # Arrange
    lang = services.get_or_create_language(session, "Go", "go")
    cat_in = services.get_or_create_category(session, "Concurrency")
    cat_out = services.get_or_create_category(session, "Web")

    q = services.create_question(session, "goroutine?", cat_in.id, lang.id)

    # Act / Assert
    all_cats = services.list_categories(session)
    assert cat_in in all_cats and cat_out in all_cats

    cats_for_lang = services.get_categories_for_language(session, lang.id)
    assert cat_in in cats_for_lang and cat_out not in cats_for_lang

    # category helper returns None if language mismatch
    assert services.get_category_by_name_and_language(session, cat_out.name, lang.id) is None


def test_diagnostic_saving(session):
    lang = services.get_or_create_language(session, "Kotlin", "kotlin")
    cat = services.get_or_create_category(session, "BasicsK")
    q = services.create_question(session, "K?',", cat.id, lang.id, is_diagnostic=True)

    user = services.get_or_create_user(session, 888)
    services.set_user_active_language(session, user.id, lang.id)
    progress = services.get_or_create_user_progress(session, user.id, lang.id)

    # first save
    ans1 = services.save_diagnostic_answer(session, progress.id, q.id, 2)
    # update same answer
    ans2 = services.save_diagnostic_answer(session, progress.id, q.id, 4)
    assert ans2.score == 4

    # save scores json
    scores = {"BasicsK": 4}
    services.save_diagnostic_scores(session, progress.id, scores)
    refreshed = session.get(type(progress), progress.id)
    assert "BasicsK" in refreshed.diagnostic_scores_json

    # mark completed
    services.mark_diagnostics_completed(session, progress.id)
    assert refreshed.diagnostics_completed is True


def test_try_populate_initial_data(session):
    # Clear languages to force branch
    session.exec(select(services.ProgrammingLanguage)).all()
    services.try_populate_initial_data()
