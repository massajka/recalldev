import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes
from src.db.db import get_session
from src.db import services
from constants import messages
from constants.callback_data import DIAGNOSTIC_SCORE_PREFIX
from src.bot.state_machine import get_user_state, set_user_state, UserState
from src.bot.flows.practice import _escape_markdown as _escape_markdown_practice, get_message_target

def _escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    return _escape_markdown_practice(text)

logger = logging.getLogger(__name__)


async def send_current_diagnostic_question(update_obj: Update | CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send the current diagnostic question to the user with scoring buttons.
    """
    """
    Send the current diagnostic question to the user with scoring buttons.
    """
    if hasattr(update_obj, 'effective_user') and update_obj.effective_user:
        telegram_id = update_obj.effective_user.id
        message_target = update_obj.message
    elif hasattr(update_obj, 'from_user') and update_obj.from_user:
        telegram_id = update_obj.from_user.id
        message_target = update_obj.message if hasattr(update_obj, 'message') else None
    else:
        return
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        current_item = services.get_current_learning_item(session, user_progress_id=user_progress.id)

        if current_item and current_item.question.is_diagnostic and current_item.status == "current":
            question_text = current_item.question.text
            category_name = current_item.question.category.name
            keyboard = [
                [InlineKeyboardButton(str(i), callback_data=f"{DIAGNOSTIC_SCORE_PREFIX}{current_item.id}_{i}") for i in range(1, 6)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            formatted_text = messages.MSG_DIAGNOSTIC_QUESTION_PROMPT.format(
                category_name=_escape_markdown(category_name),
                question_text=_escape_markdown(question_text)
            )
            try:
                await message_target.reply_text(
                    formatted_text,
                    reply_markup=reply_markup,
                    parse_mode='MarkdownV2'
                )
            except Exception:
                plain_text = f"Диагностический вопрос по теме: {category_name}\n\n{question_text}\n\nОцените свои знания по этому вопросу от 1 до 5:"
                await message_target.reply_text(
                    plain_text,
                    reply_markup=reply_markup
                )
        else:
            await message_target.reply_text(messages.MSG_NO_ACTIVE_DIAGNOSTIC_QUESTION)


async def handle_diagnostic_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the callback query when a user submits a score for a diagnostic question.
    """
    """
    Handle the callback query when a user submits a score for a diagnostic question.
    """
    query = update.callback_query
    query.answer()
    try:
        data_payload = query.data.replace(DIAGNOSTIC_SCORE_PREFIX, "")
        item_id_str, score_str = data_payload.split('_')
        item_id = int(item_id_str)
        score = int(score_str)
    except ValueError:
        logger.error(f"Invalid callback_data for diagnostic score: {query.data}")
        query.edit_message_text(messages.MSG_DIAGNOSTIC_SCORE_PARSE_ERROR)
        return
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=query.from_user.id)
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        current_item = services.get_current_learning_item(session, user_progress_id=user_progress.id)
        if not current_item or not current_item.question.is_diagnostic:
            query.edit_message_text(messages.MSG_NO_ACTIVE_DIAGNOSTIC_QUESTION)
            return
        category_name = current_item.question.category.name
        question_text = current_item.question.text
        if 'diagnostic_scores_temp' not in context.user_data:
            context.user_data['diagnostic_scores_temp'] = {}
        # Сохраняем оценку по question_id, а не по id плана
        context.user_data['diagnostic_scores_temp'][str(current_item.question_id)] = score
        # Меняем статус текущего элемента на 'answered'
        services.update_learning_item_status(session, item_id=current_item.id, status="answered")
        query.edit_message_text(
            messages.MSG_DIAGNOSTIC_SCORE_CONFIRMATION.format(
                category_name=category_name,
                question_text=question_text,
                score=score
            ),
            parse_mode='Markdown'
        )
        next_item = services.get_next_pending_learning_item(session, user_progress_id=user_progress.id)
        while next_item and not next_item.question.is_diagnostic:
            services.update_learning_item_status(session, item_id=next_item.id, status="skipped")
            next_item = services.get_next_pending_learning_item(session, user_progress_id=user_progress.id)
        if next_item:
            services.set_current_learning_item(session, user_progress_id=user_progress.id, new_current_item_id=next_item.id)
            await send_current_diagnostic_question(query, context)
        else:
            if context.user_data.get('diagnostic_scores_temp'):
                services.save_diagnostic_scores(session, user_progress_id=user_progress.id, scores=context.user_data['diagnostic_scores_temp'])
                services.mark_diagnostics_complete(session, user_progress.id)
                logger.info(f"Saved diagnostic scores for user {query.from_user.id}, progress {user_progress.id}: {context.user_data['diagnostic_scores_temp']}")
                del context.user_data['diagnostic_scores_temp']
            await query.message.reply_text(messages.MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE)
            # Автоматически генерируем практический план после диагностики
            from src.bot.callbacks import generate_practice_plan
            success, result = await generate_practice_plan(context, session, user, user_progress)
            from src.bot.flows.practice import get_message_target, send_current_practice_question
            msg = get_message_target(update)

            # Сбросить статус пользователя, чтобы разрешить повторную диагностику
            telegram_id = update.effective_user.id if hasattr(update, 'effective_user') else update.callback_query.from_user.id
            set_user_state(session, telegram_id, UserState.WAITING_FOR_ANSWER.value)

            if success:
                await msg.reply_text(messages.MSG_NEW_PRACTICE_QUESTIONS_READY.format(count=result))
                await send_current_practice_question(update, context)
            elif result == "NO_QUESTIONS":
                await msg.reply_text(messages.MSG_PRACTICE_PLAN_GENERATION_FAILED_NO_QUESTIONS)
            else:
                await msg.reply_text(messages.MSG_PRACTICE_PLAN_GENERATION_ERROR)



async def diagnostics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start the diagnostic process for the user's active language.
    """
    """
    Start the diagnostic process for the user's active language.
    """
    telegram_id = update.message.from_user.id
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        if not user.active_language_id:
            await update.message.reply_text(messages.MSG_CHOOSE_LANGUAGE_FIRST)
            return
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        if user_progress.diagnostics_completed:
            await update.message.reply_text(messages.MSG_ALREADY_IN_DIAGNOSTICS)
            return

        diagnostic_questions = services.get_diagnostic_questions(session, language_id=user.active_language_id)
        if not diagnostic_questions:
            await update.message.reply_text(messages.MSG_NO_DIAGNOSTIC_QUESTIONS_FOR_LANG)
            return
        # Полностью очищаем индивидуальный план пользователя перед диагностикой
        existing_plan_items = user_progress.learning_plan_items
        for item in existing_plan_items:
            session.delete(item)
        session.commit()
        session.refresh(user_progress)
        first_item_id = None
        for index, question in enumerate(diagnostic_questions):
            plan_item = services.add_question_to_learning_plan(
                session,
                user_progress_id=user_progress.id,
                question_id=question.id,
                order_index=index
            )
            if index == 0:
                first_item_id = plan_item.id
        if first_item_id:
            services.set_current_learning_item(
                session,
                user_progress_id=user_progress.id,
                new_current_item_id=first_item_id
            )
            context.user_data['diagnostic_scores_temp'] = {}
            await update.message.reply_text(messages.MSG_DIAGNOSTICS_STARTING_AUTO)
            await send_current_diagnostic_question(update, context)
        else:
            update.message.reply_text(messages.MSG_DIAGNOSTIC_PLAN_CREATION_FAILED)
