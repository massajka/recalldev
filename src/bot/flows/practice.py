from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.db.db import get_session
from src.db import services
from constants import messages, prompts, callback_data
from src.bot.flow_result import FlowResult, FlowStatus

async def get_current_practice_question(context: ContextTypes.DEFAULT_TYPE) -> FlowResult:
    telegram_id = context.user_data.get('telegram_id')
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        current_item = services.get_current_learning_item(session, user_progress_id=user_progress.id)
        if not current_item or not current_item.question:
            return FlowResult(FlowStatus.FINISHED)

        return FlowResult(FlowStatus.OK, {"text": current_item.question.text})

async def next_practice_question(context: ContextTypes.DEFAULT_TYPE) -> FlowResult:
    telegram_id = context.user_data.get('telegram_id')

    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        next_item = services.get_next_pending_learning_item(session, user_progress_id=user_progress.id)
        if next_item:
            services.set_current_learning_item(session, user_progress_id=user_progress.id, new_current_item_id=next_item.id)

            return FlowResult(FlowStatus.OK)

        return FlowResult(FlowStatus.FINISHED)

async def process_user_practice_answer(context: ContextTypes.DEFAULT_TYPE, answer_text: str) -> FlowResult:
    telegram_id = context.user_data.get('telegram_id')

    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        current_item = services.get_current_learning_item(session, user_progress_id=user_progress.id)
        prompt = prompts.PRACTICE_ANSWER_EVALUATION_PROMPT_TEMPLATE.format(
            category_name=current_item.question.category.name,
            question_text=current_item.question.text,
            user_answer_text=answer_text
        )
        llm = context.bot_data.get('chat_model')
        explanation = llm.invoke([{'role': 'user', 'content': prompt}]).content if llm else ''
        services.save_user_answer(
            session=session,
            user_id=user.id,
            question_id=current_item.question.id,
            learning_plan_item_id=current_item.id,
            answer_text=answer_text,
            llm_explanation=explanation
        )
        next_item = services.get_next_pending_learning_item(session, user_progress_id=user_progress.id)
        if next_item:
            keyboard = [[InlineKeyboardButton("Следующий вопрос", callback_data=callback_data.ACTION_NEXT_QUESTION)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            return FlowResult(FlowStatus.CONTINUE, {"explanation": explanation, "reply_markup": reply_markup})

        return FlowResult(
            FlowStatus.FINISHED,
            {
                "explanation": explanation,
                "finish_messages": [
                    messages.MSG_PRACTICE_PLAN_FINISHED,
                    messages.MSG_PRACTICE_PLAN_FINISHED_INSTRUCTIONS,
                ],
            },
        )
