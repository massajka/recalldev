__all__ = [
    "handle_user_answer",
    "send_current_practice_question",
    "handle_next_question_callback",
    "get_message_target",
]

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from langchain.schema import HumanMessage
from src.db.db import get_session
from src.db import services
from constants import messages, prompts
from constants.callback_data import ACTION_NEXT_QUESTION
from src.bot.state_machine import get_user_state, set_user_state, UserState

logger = logging.getLogger(__name__)

def _get_learning_item(session, item_id: int):
    """Return learning item by id from DB."""
    return services.get_learning_item_by_id(session, item_id)

def _save_user_answer(session, user, question, learning_item, user_answer_text: str, explanation: str) -> None:
    """Persist user's answer and LLM explanation, update item status."""
    services.save_user_answer(
        session=session,
        user_id=user.id,
        question_id=question.id,
        learning_plan_item_id=learning_item.id,
        answer_text=user_answer_text,
        llm_explanation=explanation
    )
    services.update_learning_item_status(session, item_id=learning_item.id, status="answered")

def _llm_explanation(context, prompt: str) -> str | None:
    """Call LLM from context.bot_data and return explanation, or None on error."""
    llm = context.bot_data.get('chat_model')
    if not llm:
        logger.error("LLM (chat_model) not found in context.bot_data for practice flow.")
        return None
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return getattr(response, 'content', None)
    except Exception as e:
        logger.error(f"LLM API call failed: {e}", exc_info=True)
        return None

def _is_llm_error(explanation: str | None) -> bool:
    """Detect if LLM explanation is an error message."""
    if not explanation:
        return True
    err_list = [
        'insufficient_quota', 'incorrect_api_key', 'invalid api key', 'you exceeded your current quota',
        'authentication', 'not found', 'rate limit', 'openai.error', 'no api key', 'no such model', 'organization is disabled'
    ]
    return any(err in str(explanation).lower() for err in err_list)

def _escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    import re
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def get_message_target(update_obj):
    if hasattr(update_obj, "message") and update_obj.message is not None:
        return update_obj.message
    elif hasattr(update_obj, "callback_query") and update_obj.callback_query is not None:
        if getattr(update_obj.callback_query, "message", None) is not None:
            return update_obj.callback_query.message
    raise RuntimeError("Cannot find a valid message object in update")

async def send_current_practice_question(update_obj: Update, context: ContextTypes.DEFAULT_TYPE, message_target_override=None) -> None:
    from src.db.db import get_session
    from src.db import services
    telegram_id = update_obj.effective_user.id if hasattr(update_obj, 'effective_user') else update_obj.from_user.id
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        current_item = services.get_current_learning_item(session, user_progress_id=user_progress.id)
        msg = get_message_target(update_obj)
        if not current_item or not current_item.question:
            await msg.reply_text("План практики не найден или вопросы закончились. Используйте /start или /diagnostics для начала нового цикла.")
            return
        await msg.reply_text(current_item.question.text)

async def handle_next_question_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback for 'Next Question' button in practice flow."""
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        # Найти следующий pending вопрос
        next_item = services.get_next_pending_learning_item(session, user_progress_id=user_progress.id)
        if next_item:
            services.set_current_learning_item(session, user_progress_id=user_progress.id, new_current_item_id=next_item.id)
            set_user_state(session, telegram_id, UserState.PRACTICE.value)
            await send_current_practice_question(update, context)
        else:
            await query.message.reply_text("Практические вопросы закончились! Вы можете начать новый цикл через /diagnostics.")


async def handle_user_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.message.from_user.id
    user_answer_text = update.message.text
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        current_item = services.get_current_learning_item(session, user_progress_id=user_progress.id)
        prompt = prompts.PRACTICE_ANSWER_EVALUATION_PROMPT_TEMPLATE.format(
    category_name=current_item.question.category.name,
    question_text=current_item.question.text,
    user_answer_text=user_answer_text
)
        explanation = _llm_explanation(context, prompt)
        services.save_user_answer(
            session=session,
            user_id=user.id,
            question_id=current_item.question.id,
            learning_plan_item_id=current_item.id,
            answer_text=user_answer_text,
            llm_explanation=explanation
        )
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        # Кнопка для перехода к следующему вопросу
        next_item = services.get_next_pending_learning_item(session, user_progress_id=user_progress.id)
        if next_item:
            # НЕ меняем current_learning_item здесь!
            keyboard = [[InlineKeyboardButton("Следующий вопрос", callback_data=ACTION_NEXT_QUESTION)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                explanation,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(explanation)
            await update.message.reply_text("Практические вопросы закончились! Вы можете начать новый цикл через /diagnostics.")
