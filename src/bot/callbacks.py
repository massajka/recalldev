import logging
import os
import json
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes
from langchain.schema import HumanMessage

from src.db.db import get_session
from src.db import services
from constants import messages, prompts
from constants.callback_data import (
    LANG_SELECT_PREFIX,
    DIAGNOSTIC_SCORE_PREFIX,
    ACTION_NEXT_QUESTION,
    ACTION_DISCUSS_ANSWER,
)


# Импортируем escape_markdown если он определён ниже, иначе определяем тут
try:
    from .views import escape_markdown
except ImportError:
    def escape_markdown(text: str) -> str:
        """Экранирует спецсимволы MarkdownV2 для Telegram."""
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


from src.bot.state_machine import UserState, get_user_state, set_user_state

from src.bot.flows.practice import handle_user_answer, send_current_practice_question, handle_next_question_callback
from src.bot.flows.diagnostics import diagnostics_command, handle_diagnostic_score, send_current_diagnostic_question


logger = logging.getLogger(__name__)

__all__ = [
    "handle_user_answer",
    "send_current_practice_question",
    "handle_next_question_callback",
    "handle_text_message",
    "diagnostics_command",
    "handle_diagnostic_score",
    "send_current_diagnostic_question",
    "handle_discuss_answer_callback",
    "practice_command",
    "start_command",
    "language_command",
    "handle_language_selection",
    "generate_practice_plan",
]



# --- Command Handlers ---


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route incoming text messages based on user state."""
    telegram_id = update.message.from_user.id
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        state = get_user_state(session, telegram_id)
        if state == UserState.PRACTICE.value or state == UserState.WAITING_FOR_ANSWER.value:
            await update.message.reply_text(messages.MSG_THANKS_FOR_ANSWER_ANALYZING)
            await handle_user_answer(update, context)
        elif state == UserState.DIAGNOSTICS.value:
            await update.message.reply_text(messages.MSG_DIAGNOSTICS_IN_PROGRESS)
        elif state == UserState.LANG_SELECT.value:
            await update.message.reply_text(messages.MSG_CHOOSE_LANGUAGE_FIRST)
        else:
            await update.message.reply_text(messages.MSG_UNKNOWN_STATE)


async def practice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /practice command: starts or resumes practice flow for the user."""
    await send_current_practice_question(update, context)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.message.from_user.id
    print(telegram_id)
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        langs = services.list_languages(session)
        keyboard = [[InlineKeyboardButton(lang.name, callback_data=f"{LANG_SELECT_PREFIX}{lang.slug}")] for lang in langs]
        await update.message.reply_text("Выберите технологию:", reply_markup=InlineKeyboardMarkup(keyboard))


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /language command to allow changing the language."""
    with get_session() as session:
        langs = services.list_languages(session)
        if not langs:
            await update.message.reply_text(messages.MSG_NO_LANGUAGES_AVAILABLE)
            return
        keyboard = [
            [InlineKeyboardButton(lang.name, callback_data=f"{LANG_SELECT_PREFIX}{lang.slug}")]
            for lang in langs
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(messages.MSG_CHOOSE_LANGUAGE, reply_markup=reply_markup)



async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    language_slug = query.data.replace(LANG_SELECT_PREFIX, "")
    with get_session() as session:
        user = get_or_create_user_by_update(session, update)
        lang = services.get_language_by_slug(session, slug=language_slug)
        services.set_user_active_language(session, user_id=user.id, language_id=lang.id)
        await query.edit_message_text(f"Вы выбрали: {lang.name} \n\nЧтобы пройти диагностику, отправьте команду /diagnostics")


async def edit_message(query, text):
    # Универсальная отправка edit_message_text для callback_query
    if hasattr(query, "edit_message_text"):
        await query.edit_message_text(text)
    else:
        logger.warning(f"Не удалось отправить edit_message_text: {text}")


def get_or_create_user_by_update(session, update):
    telegram_id = None
    if hasattr(update, "message") and update.message:
        telegram_id = update.message.from_user.id
    elif hasattr(update, "callback_query") and update.callback_query:
        telegram_id = update.callback_query.from_user.id
    if telegram_id is None:
        raise ValueError("Не удалось определить telegram_id из update")
    return services.get_or_create_user(session, telegram_id=telegram_id)

def extract_callback_data(query, prefix):
    return query.data.replace(prefix, "", 1)

def get_or_create_user_progress_for_user(session, user):
    return services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)

async def generate_practice_plan(context, session, user, user_progress):
    try:
        plan_items_count = await _generate_and_save_practice_questions(context, session, user, user_progress)
        if plan_items_count > 0:
            set_user_state(session, user.telegram_id, UserState.PRACTICE.value)
            return True, plan_items_count
        else:
            return False, "NO_QUESTIONS"
    except Exception as e:
        logger.error(f"Unexpected error in generate_practice_plan: {e}")
        return False, "ERROR"

async def send_info(update, message):
    # Универсальная отправка reply_text для message/callback_query
    if hasattr(update, "message") and update.message:
        await update.message.reply_text(message)
    elif hasattr(update, "callback_query") and update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(message)
    else:
        logger.warning(f"Не удалось отправить сообщение: {message}")

import re

def extract_json_from_llm_response(text):
    """Удаляет markdown-блоки и возвращает только JSON-строку."""
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()

async def _generate_and_save_practice_questions(context, session, user, user_progress):
    active_language = services.get_language_by_id(session, user.active_language_id)
    diagnostic_scores = json.loads(user_progress.diagnostic_scores_json)
    all_categories = services.get_categories_for_language(session, language_id=active_language.id)
    category_map = {str(cat.id): cat.name for cat in all_categories}
    formatted_scores = "\n".join([
        f"- Категория '{category_map.get(cat_id, 'Неизвестная категория ID:'+cat_id)}': Оценка {score}/5"
        for cat_id, score in diagnostic_scores.items()
    ])
    prompt_text = prompts.PRACTICE_PLAN_GENERATION_PROMPT_TEMPLATE.format(
        language_name=active_language.name,
        formatted_scores=formatted_scores,
        category_list_str=', '.join([cat.name for cat in all_categories])
    )

    llm_raw = None
    llm = context.bot_data.get('chat_model')
    if not llm:
        logger.error("LLM (chat_model) not found in context.bot_data for practice plan generation.")
        return 0
    try:
        llm_raw = llm.invoke([HumanMessage(content=prompt_text)])
        llm_response = getattr(llm_raw, 'content', None)
        if not llm_response:
            logger.error("LLM did not return any content for practice plan generation.")
            return 0
        plan_json_str = extract_json_from_llm_response(llm_response)
        plan = json.loads(plan_json_str)
    except Exception as e:
        logger.error(f"Failed to generate practice plan via LLM: {e}; LLM raw: {llm_raw}")
        return 0

    questions = plan if isinstance(plan, list) else plan.get('questions')
    if not questions or not isinstance(questions, list):
        logger.error(f"LLM plan JSON did not contain a list of questions: {plan}")
        return 0

    new_plan_items_count = 0
    first_new_item_id = None
    current_order_index = services.get_max_learning_plan_order_index(session, user_progress_id=user_progress.id) + 1
    for q in questions:
        # Найти или создать вопрос в базе по тексту и категории
        category_name = q.get("category_name") or q.get("category")
        if not category_name:
            logger.error(f"No category name in LLM question: {q}")
            continue
        category = services.get_or_create_category(session, name=category_name)
        question_text = q.get("question_text") or q.get("text")
        if not question_text:
            logger.error(f"No question text in LLM question: {q}")
            continue
        question = services.create_question(
            session=session,
            text=question_text,
            category_id=category.id,
            language_id=active_language.id,
            is_diagnostic=False
        )
        plan_item = services.add_question_to_learning_plan(
            session,
            user_progress_id=user_progress.id,
            question_id=question.id,
            order_index=current_order_index,
            status="pending"
        )
        if new_plan_items_count == 0:
            first_new_item_id = plan_item.id
        new_plan_items_count += 1
        current_order_index += 1
    if new_plan_items_count > 0 and first_new_item_id:
        services.set_current_learning_item(session, user_progress_id=user_progress.id, new_current_item_id=first_new_item_id)
    return new_plan_items_count


async def handle_discuss_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the 'Discuss Answer' button."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Ensure the prefix is correctly handled
        if not query.data.startswith(ACTION_DISCUSS_ANSWER + "_"):
            raise ValueError("Invalid prefix for discuss answer callback")
        item_id_str = query.data.split('_', 2)[-1] # Get the part after ACTION_DISCUSS_ANSWER_
        item_id = int(item_id_str)
    except (ValueError, IndexError) as e:
        logger.error(f"Invalid callback_data for discuss answer: {query.data}, error: {e}")
        await query.edit_message_text("Ошибка: не удалось определить, какой ответ обсуждать.")
        return

    with get_session() as session:
        # Fetch the UserAnswer which contains the llm_explanation
        user_answer = session.query(services.UserAnswer).filter(services.UserAnswer.learning_plan_item_id == item_id).order_by(services.UserAnswer.answered_at.desc()).first()

        if user_answer and user_answer.llm_explanation:
            await query.edit_message_reply_markup(reply_markup=None) 
            await query.message.reply_text(
                escape_markdown(f"Вот объяснение по вашему предыдущему ответу:\n\n{user_answer.llm_explanation}\n\nЧто именно вы хотели бы обсудить или уточнить? (Эта функция пока в разработке, но вы можете задать мне новый вопрос по этой теме или попросить другой пример)."),
                parse_mode='MarkdownV2'
            )
        else:
            await query.edit_message_text("Не удалось найти сохраненное объяснение для этого ответа. Возможно, оно не было сгенерировано.")
