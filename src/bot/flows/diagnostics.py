from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes
from src.db.db import get_session
from src.db import services
from constants import messages
from constants import messages, prompts, callback_data

async def get_current_diagnostic_question(context: ContextTypes.DEFAULT_TYPE):
    telegram_id = context.user_data.get('telegram_id')
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        progress_id = context.user_data.get('active_progress_id')
        if not progress_id:
            return {"status": "no_progress"}
        user_progress = session.get(services.UserProgress, progress_id)
        question_ids = context.user_data.get('diagnostic_question_ids', [])
        current_index = context.user_data.get('diagnostic_current_index', 0)
        if not question_ids:
            return {"status": "no_questions"}
        if current_index >= len(question_ids):
            return {"status": "done"}
        question_id = question_ids[current_index]
        question = services.get_question_by_id(session, question_id)
        if not question:
            return {"status": "not_found"}
        question_text = question.text
        category_name = question.category.name
        keyboard = [[InlineKeyboardButton(str(i), callback_data=f"{callback_data.DIAGNOSTIC_SCORE_PREFIX}{question_id}_{i}") for i in range(1, 6)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = messages.MSG_DIAGNOSTIC_QUESTION_PROMPT.format(category_name=category_name, question_text=question_text)
        return {
            "status": "ok",
            "text": text,
            "reply_markup": reply_markup
        }

async def start_diagnostics(context: ContextTypes.DEFAULT_TYPE) -> dict:
    telegram_id = context.user_data.get('telegram_id')
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        if not user.active_language_id:
            return {"status": "no_language"}
        # Используем уже существующий прогресс, если он есть, иначе создаём новый.
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        # Если ранее диагностика была завершена, обнулим результаты, чтобы начать заново.
        user_progress.diagnostic_scores_json = None
        user_progress.diagnostics_completed = False
        session.add(user_progress)
        session.commit()
        session.refresh(user_progress)
        context.user_data['active_progress_id'] = user_progress.id
        diagnostic_questions = services.get_diagnostic_questions(session, language_id=user.active_language_id)
        if not diagnostic_questions:
            context.user_data['diagnostic_current_index'] = 0
            context.user_data['diagnostic_question_ids'] = []
            return {"status": "no_questions"}
        context.user_data['diagnostic_current_index'] = 0
        context.user_data['diagnostic_question_ids'] = [q.id for q in diagnostic_questions]
        context.user_data['diagnostic_scores_temp'] = {}
        return {"status": "ok"}

async def process_diagnostic_score(context: ContextTypes.DEFAULT_TYPE, question_id: int, score: int) -> dict:
    progress_id = context.user_data.get('active_progress_id')
    question_ids = context.user_data.get('diagnostic_question_ids', [])
    current_index = context.user_data.get('diagnostic_current_index', 0)
    if progress_id is None or current_index >= len(question_ids):
        return {"status": "no_active_question"}
    with get_session() as session:
        user_progress = session.get(services.UserProgress, progress_id)
        services.save_diagnostic_answer(session, user_progress.id, question_id, score)
        next_index = current_index + 1
        context.user_data['diagnostic_current_index'] = next_index
        if next_index < len(question_ids):
            return {"status": "next_question"}
        else:
            services.mark_diagnostics_completed(session, user_progress.id)
            return {"status": "completed"}
