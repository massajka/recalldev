from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from constants import callback_data, messages
from src.bot.flow_result import FlowResult, FlowStatus
from src.db import services
from src.db.db import get_session


async def get_current_diagnostic_question(
    context: ContextTypes.DEFAULT_TYPE,
) -> FlowResult:
    telegram_id = context.user_data.get("telegram_id")
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        progress_id = context.user_data.get("active_progress_id")
        if not progress_id:
            # Automatically start diagnostics to avoid sending an error message to the user
            start_res = await start_diagnostics(context)
            if start_res.status != FlowStatus.OK:
                return start_res
            progress_id = context.user_data.get("active_progress_id")
            # After auto-start, refresh diagnostic question IDs and current index from context
            question_ids = context.user_data.get("diagnostic_question_ids", [])
            current_index = context.user_data.get("diagnostic_current_index", 0)

        user_progress = session.get(services.UserProgress, progress_id)
        question_ids = context.user_data.get("diagnostic_question_ids", [])
        current_index = context.user_data.get("diagnostic_current_index", 0)

        if not question_ids:
            return FlowResult(FlowStatus.NO_QUESTIONS)

        if current_index >= len(question_ids):
            return FlowResult(FlowStatus.DONE)

        question_id = question_ids[current_index]
        question = services.get_question_by_id(session, question_id)

        if not question:
            return FlowResult(FlowStatus.ERROR)

        question_text = question.text
        category_name = question.category.name
        keyboard = [
            [
                InlineKeyboardButton(
                    str(i),
                    callback_data=f"{callback_data.DIAGNOSTIC_SCORE_PREFIX}{question_id}_{i}",
                )
                for i in range(1, 6)
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = messages.MSG_DIAGNOSTIC_QUESTION_PROMPT.format(
            category_name=category_name, question_text=question_text
        )

        return FlowResult(FlowStatus.OK, {"text": text, "reply_markup": reply_markup})


async def start_diagnostics(context: ContextTypes.DEFAULT_TYPE) -> FlowResult:
    telegram_id = context.user_data.get("telegram_id")
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        if not user.active_language_id:
            return FlowResult(FlowStatus.NO_LANGUAGE)
        # Use existing progress if it exists, otherwise create a new one.
        user_progress = services.get_or_create_user_progress(
            session, user_id=user.id, language_id=user.active_language_id
        )
        # If the previous diagnosis was completed, reset the results to start over.
        user_progress.diagnostic_scores_json = None
        user_progress.diagnostics_completed = False

        session.add(user_progress)
        session.commit()
        session.refresh(user_progress)

        context.user_data["active_progress_id"] = user_progress.id
        diagnostic_questions = services.get_diagnostic_questions(
            session, language_id=user.active_language_id
        )

        if not diagnostic_questions:
            context.user_data["diagnostic_current_index"] = 0
            context.user_data["diagnostic_question_ids"] = []

            return FlowResult(FlowStatus.NO_QUESTIONS)

        context.user_data["diagnostic_current_index"] = 0
        context.user_data["diagnostic_question_ids"] = [
            q.id for q in diagnostic_questions
        ]
        context.user_data["diagnostic_scores_temp"] = {}

        # Immediately return the first diagnostic question so the user sees only one message.
        first_q = await get_current_diagnostic_question(context)
        # Advance index so subsequent calls fetch the next question instead of repeating.
        context.user_data["diagnostic_current_index"] += 1

        return first_q


async def process_diagnostic_score(
    context: ContextTypes.DEFAULT_TYPE, question_id: int, score: int
) -> FlowResult:
    progress_id = context.user_data.get("active_progress_id")
    question_ids = context.user_data.get("diagnostic_question_ids", [])
    current_index = context.user_data.get("diagnostic_current_index", 0)

    if progress_id is None or current_index >= len(question_ids):
        return FlowResult(FlowStatus.NO_ACTIVE_QUESTION)

    with get_session() as session:
        user_progress = session.get(services.UserProgress, progress_id)
        services.save_diagnostic_answer(session, user_progress.id, question_id, score)
        next_index = current_index + 1
        context.user_data["diagnostic_current_index"] = next_index

        if next_index < len(question_ids):
            return FlowResult(FlowStatus.NEXT_QUESTION)
        else:
            services.mark_diagnostics_completed(session, user_progress.id)

            return FlowResult(FlowStatus.COMPLETED)
