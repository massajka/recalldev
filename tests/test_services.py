"""All service-layer tests consolidated into a single file.
Each class below represents an *area* of service functionality,
and every method inside a class is a test-case for that area.
"""

import copy

import pytest
from sqlmodel import select

from src.db import services


class TestLearningPlanCore:
    def test_learning_plan_lifecycle(self, session):
        lang = services.get_or_create_language(session, name="JS", slug="js")
        cat = services.get_or_create_category(session, name="Async")
        q = services.create_question(
            session, text="Explain Promise", category_id=cat.id, language_id=lang.id
        )

        user = services.get_or_create_user(session, telegram_id=42)
        services.set_user_active_language(session, user.id, lang.id)

        progress = services.get_or_create_user_progress(session, user.id, lang.id)
        item = services.add_question_to_learning_plan(
            session, progress.id, q.id, order_index=0
        )
        assert services.user_has_practice_plan(session, progress.id)

        # current item lifecycle
        assert services.get_current_learning_item(session, progress.id) is None
        services.set_current_learning_item(session, progress.id, item.id)
        assert services.get_current_learning_item(session, progress.id) == item


class TestServiceGetters:
    def test_getters_by_id(self, session):
        lang = services.get_or_create_language(session, name="Swift", slug="swift")
        cat = services.get_or_create_category(session, name="Memory")
        q = services.create_question(
            session, text="ARC?", category_id=cat.id, language_id=lang.id
        )

        assert services.get_language_by_id(session, lang.id).slug == "swift"
        assert services.get_question_by_id(session, q.id).text == "ARC?"

        found_cat = services.get_category_by_name_and_language(
            session, cat.name, lang.id
        )
        assert found_cat.id == cat.id


class TestServicesMisc:
    def test_category_helpers(self, session):
        lang = services.get_or_create_language(session, "Go", "go")
        cat_in = services.get_or_create_category(session, "Concurrency")
        cat_out = services.get_or_create_category(session, "Web")
        services.create_question(session, "goroutine?", cat_in.id, lang.id)

        all_cats = services.list_categories(session)
        assert cat_in in all_cats and cat_out in all_cats

        cats_for_lang = services.get_categories_for_language(session, lang.id)
        assert cat_in in cats_for_lang and cat_out not in cats_for_lang

        assert (
            services.get_category_by_name_and_language(session, cat_out.name, lang.id)
            is None
        )

    def test_diagnostic_saving(self, session):
        lang = services.get_or_create_language(session, "Kotlin", "kotlin")
        cat = services.get_or_create_category(session, "BasicsK")
        q = services.create_question(
            session, "K?'", cat.id, lang.id, is_diagnostic=True
        )

        user = services.get_or_create_user(session, 888)
        services.set_user_active_language(session, user.id, lang.id)
        progress = services.get_or_create_user_progress(session, user.id, lang.id)

        services.save_diagnostic_answer(session, progress.id, q.id, 2)
        ans2 = services.save_diagnostic_answer(session, progress.id, q.id, 4)
        assert ans2.score == 4

        scores = {"BasicsK": 4}
        services.save_diagnostic_scores(session, progress.id, scores)
        refreshed = session.get(type(progress), progress.id)
        assert "BasicsK" in refreshed.diagnostic_scores_json

        services.mark_diagnostics_completed(session, progress.id)
        assert refreshed.diagnostics_completed is True

    def test_plan_order_and_next(self, session):
        lang = services.get_or_create_language(session, name="C#", slug="csharp")
        cat = services.get_or_create_category(session, name="LINQ")
        q1 = services.create_question(session, "q1", cat.id, lang.id)
        q2 = services.create_question(session, "q2", cat.id, lang.id)

        user = services.get_or_create_user(session, telegram_id=51)
        progress = services.get_or_create_user_progress(session, user.id, lang.id)

        it1 = services.add_question_to_learning_plan(session, progress.id, q1.id, 0)
        it2 = services.add_question_to_learning_plan(session, progress.id, q2.id, 1)

        assert it2.order_index == it1.order_index + 1
        assert services.get_next_pending_learning_item(session, progress.id) == it1


class TestServicesFullCoverage:
    def test_services_full_coverage(self, session, monkeypatch):
        base_count = len(services.list_languages(session))
        lang = services.get_or_create_language(session, "Rust", "rust")
        assert len(services.list_languages(session)) >= base_count

        # Category may exist from previous tests; ensure retrieval works
        existing_cat = services.get_category_by_name(session, "Memory")
        if existing_cat:
            assert existing_cat.name == "Memory"
        cat = services.get_or_create_category(session, "Memory")
        assert (
            services.get_category_by_name_and_language(session, "Memory", lang.id)
            is None
        )
        q = services.create_question(session, "Ownership?", cat.id, lang.id)
        assert (
            services.get_category_by_name_and_language(session, cat.name, lang.id)
            == cat
        )

        user = services.get_or_create_user(session, 1001)
        prog = services.get_or_create_user_progress(session, user.id, lang.id)
        assert services.user_has_practice_plan(session, prog.id) is False
        item = services.add_question_to_learning_plan(session, prog.id, q.id, 0)
        assert services.user_has_practice_plan(session, prog.id) is True

        services.save_diagnostic_scores(session, prog.id, {"s": 3})
        services.update_learning_item_status(session, item.id, "answered")

        bad_data = copy.deepcopy(services.INITIAL_DATA)
        bad_data["diagnostic_questions"] = {"rust": [{"category": "U", "text": "bad"}]}
        monkeypatch.setattr(services, "INITIAL_DATA", bad_data, raising=False)
        services.populate_initial_data(session)
        monkeypatch.setattr(
            services,
            "INITIAL_DATA",
            copy.deepcopy(services.INITIAL_DATA),
            raising=False,
        )
        services.try_populate_initial_data()


class TestPopulateInitialData:
    def test_populate_initial_data(self, session):
        services.populate_initial_data(session)
        langs = session.exec(select(services.ProgrammingLanguage)).all()
        cats = session.exec(select(services.Category)).all()
        qs = session.exec(select(services.Question)).all()
        assert len(langs) >= 3 and len(cats) >= 3 and any(q.is_diagnostic for q in qs)
