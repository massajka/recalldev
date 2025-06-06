import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging
from typing import Optional, Dict

from sqlmodel import SQLModel, Session, select
# Импортируем engine и get_session из db.py
from src.db.db import engine, get_session
from src.db.models import ProgrammingLanguage, Category, Question

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Hardcoded Initial Data ---
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
        {"name": "Базы данных"},
        {"name": "Сетевое взаимодействие"},
        {"name": "Тестирование"},
        {"name": "Инструменты и экосистема"},
        {"name": "Асинхронность и параллелизм"} # Добавлено, т.к. используется в вопросах JS
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

# --- Hardcoded Helper Functions for Data Population (adapted from services.py) ---
def _get_or_create_language(session: Session, name: str, slug: str) -> ProgrammingLanguage:
    language = session.exec(select(ProgrammingLanguage).where(ProgrammingLanguage.slug == slug)).first()
    if not language:
        language = ProgrammingLanguage(name=name, slug=slug)
        session.add(language)
        # session.commit() / session.refresh() будут вызываться один раз в конце populate_initial_data_hardcoded
        logger.info(f"Prepared language for creation: {name} ({slug})")
    return language

def _get_or_create_category(session: Session, name: str, description: Optional[str] = None) -> Category:
    category = session.exec(select(Category).where(Category.name == name)).first()
    if not category:
        category = Category(name=name, description=description)
        session.add(category)
        logger.info(f"Prepared category for creation: {name}")
    return category

def _create_question(session: Session, text: str, category_id: int, language_id: int, 
                    is_diagnostic: bool = False, author_notes: Optional[str] = None) -> Optional[Question]:
    existing_question = session.exec(
        select(Question)
        .where(Question.text == text)
        .where(Question.category_id == category_id)
        .where(Question.language_id == language_id)
    ).first()
    if existing_question:
        logger.warning(f"Question with text '{text}' for lang_id={language_id}, cat_id={category_id} already exists. Skipping.")
        return None # Возвращаем None, чтобы показать, что ничего не было добавлено
        
    question = Question(
        text=text, 
        category_id=category_id, 
        language_id=language_id, 
        is_diagnostic=is_diagnostic, 
        author_notes=author_notes
    )
    session.add(question)
    logger.info(f"Prepared question for creation: {text[:50]}... for lang_id={language_id}, cat_id={category_id}")
    return question

def populate_initial_data_hardcoded(session: Session):
    logger.info("Populating initial data (hardcoded version)...")
    
    lang_map: Dict[str, ProgrammingLanguage] = {}
    for lang_data in INITIAL_DATA["languages"]:
        lang = _get_or_create_language(session, name=lang_data["name"], slug=lang_data["slug"])
        if lang: # Если язык был только что подготовлен (или уже существовал и был получен)
             lang_map[lang_data["slug"]] = lang

    cat_map: Dict[str, Category] = {}
    for cat_data in INITIAL_DATA["categories"]:
        cat = _get_or_create_category(session, name=cat_data["name"])
        if cat:
            cat_map[cat_data["name"]] = cat

    # Commit languages and categories first to get their IDs if they are new
    # Однако, если они уже существуют, commit не нужен. 
    # Для простоты, и так как _get_or_create_* не делают commit, 
    # мы сделаем один commit в конце, после добавления всех объектов.
    # Это требует, чтобы объекты Language и Category уже имели ID, если они существуют,
    # или чтобы SQLAlchemy обработал зависимости при финальном коммите.
    # Для большей надежности, можно было бы сделать commit после языков и категорий,
    # а затем refresh, но попробуем так для начала.

    questions_added_count = 0
    for lang_slug, questions_data in INITIAL_DATA["diagnostic_questions"].items():
        language = lang_map.get(lang_slug)
        if not language:
            logger.warning(f"Language slug '{lang_slug}' for diagnostic questions not found in loaded languages. Skipping questions for this language.")
            continue
        
        for q_data in questions_data:
            category = cat_map.get(q_data["category"])
            if not category:
                logger.warning(f"Category '{q_data['category']}' for diagnostic question '{q_data['text'][:30]}...' not found in loaded categories. Skipping this question.")
                continue
            
            # Убедимся, что language.id и category.id доступны.
            # Если они только что созданы и не закоммичены, SQLAlchemy может не знать их ID.
            # Однако, если мы добавляем все в сессию и делаем один commit, SQLAlchemy должен разобраться.
            # Для большей явности, можно было бы сделать session.flush() после добавления языков/категорий
            # чтобы получить их ID до создания вопросов.

            # Проверка на случай, если язык или категория были только что созданы и еще не имеют ID до flush/commit
            # Это более безопасный подход, если не делать flush после создания языков/категорий
            temp_lang_id = language.id
            temp_cat_id = category.id
            if temp_lang_id is None or temp_cat_id is None:
                logger.info("Flushing session to obtain IDs for newly created languages/categories before creating questions...")
                session.flush() # Получаем ID для объектов, добавленных в сессию
                temp_lang_id = language.id
                temp_cat_id = category.id
            
            if temp_lang_id is None or temp_cat_id is None:
                logger.error(f"Could not obtain ID for language '{language.name}' or category '{category.name}'. Skipping question '{q_data['text'][:30]}...'")
                continue

            created_q = _create_question(
                session=session,
                text=q_data["text"],
                category_id=temp_cat_id,
                language_id=temp_lang_id,
                is_diagnostic=q_data.get("is_diagnostic", True),
                author_notes=q_data.get("notes")
            )
            if created_q:
                questions_added_count += 1
    
    if session.new or session.dirty: # Проверяем, есть ли что коммитить
        logger.info(f"Committing {len(session.new)} new objects and {len(session.dirty)} dirty objects to the database.")
        session.commit()
        logger.info("Initial data committed to the database.")
        # Обновлять (refresh) объекты здесь не обязательно, т.к. скрипт завершается.
    else:
        logger.info("No new or modified data to commit for initial population (data likely already exists).")
    logger.info(f"Initial data population (hardcoded version) complete. Added {questions_added_count} new questions.")

def create_and_populate_database():
    logger.info("Attempting to create database tables...")
    logger.info(f"Using database engine: {engine.url}")
    if engine.echo:
        logger.info("SQLAlchemy engine echo is True, SQL statements will be logged.")

    try:
        SQLModel.metadata.create_all(engine)
        logger.info("Database tables created successfully (or already existed).")
        
        logger.info("Attempting to populate initial data (hardcoded version)...")
        with get_session() as session:
            populate_initial_data_hardcoded(session)
        logger.info("Initial data population attempt (hardcoded version) complete.")

    except Exception as e:
        logger.exception("CRITICAL: An error occurred during database creation or initial data population.")

if __name__ == "__main__":
    logger.info("Executing script to create database tables and populate initial data (hardcoded version)...")
    create_and_populate_database()
    logger.info("Script execution finished.")
