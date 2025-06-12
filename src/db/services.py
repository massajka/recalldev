import datetime

from sqlmodel import select, Session
from src.db.db import get_session, engine # engine нужен для create_all в populate_initial_data
from src.db.models import (
    ProgrammingLanguage,
    User,
    Category,
    Question,
    UserProgress,
    UserLearningPlanItem,
    UserAnswer,
    SQLModel # Для SQLModel.metadata.create_all
)
from typing import List, Optional, Dict
import json
import logging

logger = logging.getLogger(__name__)

# --- ProgrammingLanguage Services ---
def get_or_create_language(session: Session, name: str, slug: str) -> ProgrammingLanguage:
    language = session.exec(select(ProgrammingLanguage).where(ProgrammingLanguage.slug == slug)).first()
    if not language:
        language = ProgrammingLanguage(name=name, slug=slug)
        session.add(language)
        session.commit()
        session.refresh(language)
        logger.info(f"Created language: {name} ({slug})")
    return language

def get_language_by_id(session: Session, language_id: int) -> Optional[ProgrammingLanguage]:
    return session.get(ProgrammingLanguage, language_id)

def get_language_by_slug(session: Session, slug: str) -> Optional[ProgrammingLanguage]:
    return session.exec(select(ProgrammingLanguage).where(ProgrammingLanguage.slug == slug)).first()

def list_languages(session: Session) -> List[ProgrammingLanguage]:
    return session.exec(select(ProgrammingLanguage)).all()

# --- Category Services ---
def get_or_create_category(session: Session, name: str, description: Optional[str] = None) -> Category:
    category = session.exec(select(Category).where(Category.name == name)).first()
    if not category:
        category = Category(name=name, description=description)
        session.add(category)
        session.commit()
        session.refresh(category)
        logger.info(f"Created category: {name}")
    return category

def get_category_by_name(session: Session, name: str) -> Optional[Category]:
    return session.exec(select(Category).where(Category.name == name)).first()

def get_category_by_name_and_language(session: Session, name: str, language_id: int) -> Optional[Category]:
    """
    Найти категорию по имени и языку (через наличие хотя бы одного вопроса с этой категорией и языком).
    Возвращает Category или None.
    """
    category = session.exec(select(Category).where(Category.name == name)).first()
    if not category:
        return None
    from .models import Question
    question_exists = session.exec(
        select(Question).where(
            Question.category_id == category.id,
            Question.language_id == language_id
        )
    ).first()
    if question_exists:
        return category
    return None

def list_categories(session: Session) -> List[Category]:
    return session.exec(select(Category)).all()

def get_categories_for_language(session: Session, language_id: int) -> List[Category]:
    """
    Retrieves all categories that have at least one question associated with the given language.
    """
    # Find all unique category_ids from questions linked to the given language_id
    stmt_category_ids = (
        select(Question.category_id)
        .where(Question.language_id == language_id)
        .distinct()
    )
    # session.exec(...).all() for a single selected column returns a list of tuples, e.g., [(1,), (2,)]
    category_id_tuples = session.exec(stmt_category_ids).all()

    if not category_id_tuples:
        return []

    # Extract the actual IDs, filtering out potential None values. 
    # session.exec(select(Model.column)).all() returns a list of values, not tuples, for a single column.
    actual_ids = [cat_id for cat_id in category_id_tuples if cat_id is not None]

    if not actual_ids:
        return []

    stmt_categories = select(Category).where(Category.id.in_(actual_ids))
    categories = session.exec(stmt_categories).all()
    return categories

# --- User Services ---
def create_user(session: Session, telegram_id: int, ui_language_code: str = "ru") -> User:

    user = User(telegram_id=telegram_id, ui_language_code=ui_language_code)
    session.add(user)
    session.commit()
    session.refresh(user)
    logger.info(f"Created user: {telegram_id}")

    return user

def get_or_create_user(session: Session, telegram_id: int, ui_language_code: str = "ru") -> User:
    user = session.exec(select(User).where(User.telegram_id == telegram_id)).first()
    if user:
        return user
    return create_user(session, telegram_id, ui_language_code)



def set_user_active_language(session: Session, user_id: int, language_id: int) -> Optional[User]:
    user = session.get(User, user_id)
    if user:
        user.active_language_id = language_id
        session.add(user)
        session.commit()
        session.refresh(user)
        logger.info(f"Set active language for user {user_id} to {language_id}")
    return user

# --- Question Services ---
def create_question(session: Session, text: str, category_id: int, language_id: int, 
                    is_diagnostic: bool = False, author_notes: Optional[str] = None) -> Question:
    # Check if a similar question already exists to avoid duplicates
    existing_question = session.exec(
        select(Question)
        .where(Question.text == text)
        .where(Question.category_id == category_id)
        .where(Question.language_id == language_id)
    ).first()
    if existing_question:
        logger.warning(f"Question with text '{text}' for lang_id={language_id}, cat_id={category_id} already exists.")
        return existing_question
        
    question = Question(
        text=text, 
        category_id=category_id, 
        language_id=language_id, 
        is_diagnostic=is_diagnostic, 
        author_notes=author_notes
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    logger.info(f"Created question: {text[:50]}... for lang_id={language_id}, cat_id={category_id}")
    return question

def get_diagnostic_questions(session: Session, language_id: int, category_id: Optional[int] = None) -> List[Question]:
    statement = select(Question).where(Question.language_id == language_id).where(Question.is_diagnostic == True)
    if category_id:
        statement = statement.where(Question.category_id == category_id)
    return session.exec(statement).all()

def get_question_by_id(session: Session, question_id: int) -> Optional[Question]:
    return session.get(Question, question_id)

# --- UserProgress & UserLearningPlanItem Services ---
def get_learning_plan_items(session: Session, user_progress_id: int) -> List[UserLearningPlanItem]:
    return session.exec(
        select(UserLearningPlanItem).where(UserLearningPlanItem.user_progress_id == user_progress_id)
    ).all()


def mark_diagnostics_completed(session: Session, user_progress_id: int):
    progress = session.get(UserProgress, user_progress_id)
    if progress:
        progress.diagnostics_completed = True
        session.add(progress)
        session.commit()
        session.refresh(progress)
    return progress


def get_max_learning_plan_order_index(session: Session, user_progress_id: int) -> int:
    """
    Возвращает максимальный order_index для всех UserLearningPlanItem данного user_progress_id.
    Если элементов нет, возвращает -1.
    """
    result = session.exec(
        select(UserLearningPlanItem.order_index)
        .where(UserLearningPlanItem.user_progress_id == user_progress_id)
        .order_by(UserLearningPlanItem.order_index.desc())
    ).first()
    return result if result is not None else -1

def create_new_user_progress(session, user_id, language_id):
    """Создаёт новый прогресс пользователя для выбранной технологии."""
    from src.db.models import UserProgress
    user_progress = UserProgress(
        user_id=user_id,
        language_id=language_id,
        diagnostic_scores_json=None,
        diagnostics_completed=False
    )
    session.add(user_progress)
    session.commit()
    session.refresh(user_progress)
    logger.info(f"Created UserProgress for user {user_id}, language {language_id}")

    return user_progress

def get_or_create_user_progress(session, user_id, language_id): 
    progress = session.exec(
        select(UserProgress)
        .where(UserProgress.user_id == user_id)
        .where(UserProgress.language_id == language_id)
    ).first()

    return progress or create_new_user_progress(session, user_id, language_id)

def add_question_to_learning_plan(session: Session, user_progress_id: int, question_id: int, order_index: int, status: str = "pending") -> UserLearningPlanItem:
    # Check if this question at this order_index already exists for this plan
    # Удаляем все старые элементы для этого user_progress_id и question_id (любой order_index)
    old_items = session.exec(
        select(UserLearningPlanItem)
        .where(UserLearningPlanItem.user_progress_id == user_progress_id)
        .where(UserLearningPlanItem.question_id == question_id)
    ).all()
    for old_item in old_items:
        session.delete(old_item)
    session.commit()

    item = UserLearningPlanItem(
        user_progress_id=user_progress_id,
        question_id=question_id,
        order_index=order_index,
        status=status
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    logger.info(f"Added question {question_id} to plan for progress {user_progress_id} at index {order_index}")
    return item


def get_learning_item_by_id(session: Session, item_id: int) -> Optional[UserLearningPlanItem]:
    return session.get(UserLearningPlanItem, item_id)

def get_current_learning_item(session: Session, user_progress_id: int) -> Optional[UserLearningPlanItem]:
    return session.exec(
        select(UserLearningPlanItem)
        .where(UserLearningPlanItem.user_progress_id == user_progress_id)
        .where(UserLearningPlanItem.status == "current")
    ).first()

def get_next_pending_learning_item(session: Session, user_progress_id: int, current_order_index: Optional[int] = -1) -> Optional[UserLearningPlanItem]:
    statement = (
        select(UserLearningPlanItem)
        .where(UserLearningPlanItem.user_progress_id == user_progress_id)
        .where(UserLearningPlanItem.status == "pending")
    )
    if current_order_index is not None:
         statement = statement.where(UserLearningPlanItem.order_index > current_order_index)
    
    return session.exec(statement.order_by(UserLearningPlanItem.order_index)).first()

def update_learning_item_status(session: Session, item_id: int, status: str) -> Optional[UserLearningPlanItem]:
    item = session.get(UserLearningPlanItem, item_id)
    if item:
        item.status = status
        session.add(item)
        session.commit()
        session.refresh(item)
        logger.info(f"Updated status of learning item {item_id} to {status}")
    return item

def set_current_learning_item(session: Session, user_progress_id: int, new_current_item_id: int) -> Optional[UserLearningPlanItem]:
    # Сбросить все другие current для этого user_progress_id
    current_items = session.exec(
        select(UserLearningPlanItem)
        .where(UserLearningPlanItem.user_progress_id == user_progress_id)
        .where(UserLearningPlanItem.status == "current")
    ).all()
    for item in current_items:
        if item.id != new_current_item_id:
            item.status = "answered"
            session.add(item)
    session.commit()

    new_item = session.get(UserLearningPlanItem, new_current_item_id)
    if new_item:
        new_item.status = "current"
        session.add(new_item)
        session.commit()
        session.refresh(new_item)
        logger.info(f"Set learning item {new_current_item_id} to 'current' for progress {user_progress_id}")
        return new_item
    return None

def save_diagnostic_scores(session: Session, user_progress_id: int, scores: Dict[str, int]):
    progress = session.get(UserProgress, user_progress_id)
    if progress:
        progress.diagnostic_scores_json = json.dumps(scores, ensure_ascii=False)
        session.add(progress)
        session.commit()
        session.refresh(progress)
        logger.info(f"Saved diagnostic scores for progress {user_progress_id}")
    return progress

# --- UserDiagnosticAnswer Services ---
def save_diagnostic_answer(session: Session, user_progress_id: int, question_id: int, score: int):
    from src.db.models import UserDiagnosticAnswer
    answer = session.exec(
        select(UserDiagnosticAnswer)
        .where(UserDiagnosticAnswer.user_progress_id == user_progress_id)
        .where(UserDiagnosticAnswer.question_id == question_id)
    ).first()
    if answer:
        answer.score = score
        answer.answered_at = datetime.datetime.utcnow()
        session.add(answer)
        session.commit()
        session.refresh(answer)
    else:
        answer = UserDiagnosticAnswer(
            user_progress_id=user_progress_id,
            question_id=question_id,
            score=score
        )
        session.add(answer)
        session.commit()
        session.refresh(answer)
    return answer

def get_diagnostic_answers_for_progress(session: Session, user_progress_id: int):
    from src.db.models import UserDiagnosticAnswer
    return session.exec(
        select(UserDiagnosticAnswer)
        .where(UserDiagnosticAnswer.user_progress_id == user_progress_id)
    ).all()

# --- UserAnswer Services ---
def save_user_answer(session: Session, user_id: int, question_id: int, learning_plan_item_id: int, 
                     answer_text: str, llm_assessment: Optional[str] = None, 
                     llm_explanation: Optional[str] = None, 
                     is_correct_by_llm: Optional[bool] = None) -> UserAnswer:
    answer = UserAnswer(
        user_id=user_id,
        question_id=question_id,
        learning_plan_item_id=learning_plan_item_id,
        answer_text=answer_text,
        llm_assessment=llm_assessment,
        llm_explanation=llm_explanation,
        is_correct_by_llm=is_correct_by_llm
    )
    session.add(answer)
    session.commit()
    session.refresh(answer)
    logger.info(f"Saved answer for user {user_id}, question {question_id}, item {learning_plan_item_id}")
    return answer

# --- Data Population (Optional, for initial setup) ---
INITIAL_DATA = {
    "languages": [
        {"name": "Python", "slug": "python"},
        {"name": "JavaScript", "slug": "javascript"},
        {"name": "Общие вопросы", "slug": "general"} # For general CS questions
    ],
    "categories": [
        {"name": "Основы языка"},
        {"name": "Структуры данных"},
        {"name": "Алгоритмы"},
        {"name": "ООП (Объектно-ориентированное программирование)"},
        {"name": "Асинхронность и параллелизм"},
        {"name": "Базы данных"},
        {"name": "Сетевое взаимодействие"},
        {"name": "Тестирование"},
        {"name": "Инструменты и экосистема"}
    ],
    "diagnostic_questions": {
        "python": [
            {"category": "Основы языка", "text": "Какие основные типы данных в Python вы знаете? Приведите примеры.", "notes": "Ожидается перечисление int, float, str, list, tuple, dict, set, bool.", "is_diagnostic": True},
            {"category": "Структуры данных", "text": "Чем отличаются списки (list) от кортежей (tuple) в Python?", "notes": "Изменяемость, производительность для некоторых операций, использование.", "is_diagnostic": True},
            {"category": "ООП (Объектно-ориентированное программирование)", "text": "Что такое декоратор в Python и как его создать?", "notes": "Функция, принимающая другую функцию и расширяющая её поведение.", "is_diagnostic": True}
        ],
        "javascript": [
            {"category": "Основы языка", "text": "Что такое замыкание (closure) в JavaScript? Приведите пример.", "is_diagnostic": True},
            {"category": "Асинхронность и параллелизм", "text": "Объясните разницу между `let`, `const` и `var` в JavaScript.", "is_diagnostic": True}
        ]
    }
}

def populate_initial_data(session: Session):
    logger.info("Populating initial data...")
    
    # Create Languages
    lang_map = {}
    for lang_data in INITIAL_DATA["languages"]:
        lang = get_or_create_language(session, name=lang_data["name"], slug=lang_data["slug"])
        lang_map[lang_data["slug"]] = lang

    # Create Categories
    cat_map = {}
    for cat_data in INITIAL_DATA["categories"]:
        cat = get_or_create_category(session, name=cat_data["name"])
        cat_map[cat_data["name"]] = cat

    # Create Diagnostic Questions
    for lang_slug, questions_data in INITIAL_DATA["diagnostic_questions"].items():
        language = lang_map.get(lang_slug)
        if not language:
            logger.warning(f"Language slug '{lang_slug}' for diagnostic questions not found in loaded languages. Skipping.")
            continue
        
        for q_data in questions_data:
            category = cat_map.get(q_data["category"])
            if not category:
                logger.warning(f"Category '{q_data['category']}' for diagnostic question not found. Skipping question: {q_data['text'][:30]}...")
                continue
            
            create_question(
                session=session,
                text=q_data["text"],
                category_id=category.id,
                language_id=language.id,
                is_diagnostic=q_data.get("is_diagnostic", True),
                author_notes=q_data.get("notes")
            )
    logger.info("Initial data population complete.")

# Helper to run populate_initial_data if needed (e.g., on first app start)
# This should be called carefully, e.g., after init_db and perhaps only once.
def try_populate_initial_data():
    # This is a simple check. For production, you might want a more robust way
    # to ensure this runs only once (e.g., check a flag in DB or a config file).
    with get_session() as session:
        if not session.exec(select(ProgrammingLanguage)).first(): # Check if languages are missing
            logger.info("No languages found, attempting to populate initial data.")
            # Ensure tables are created before populating
            SQLModel.metadata.create_all(engine) # Make sure this is safe to call multiple times
            populate_initial_data(session)
        else:
            logger.info("Initial data (languages) already present. Skipping population.")
