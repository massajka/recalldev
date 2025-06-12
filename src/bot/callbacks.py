import logging
import json
import re

from langchain.schema import HumanMessage

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.db.db import get_session
from src.db import services
from src.bot.state_machine import get_user_state, UserState, set_user_state
from src.bot.flows import diagnostics as diagnostics_flow
from src.bot.flows import practice as practice_flow
from constants import messages, prompts, callback_data

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    context.user_data['telegram_id'] = telegram_id  # Важно для flows
    with get_session() as session:
        services.get_or_create_user(session, telegram_id=telegram_id)
    await update.message.reply_text(messages.MSG_GREETING)
    await technology_command(update, context)

async def diagnostics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    context.user_data['telegram_id'] = telegram_id
    result = await diagnostics_flow.start_diagnostics(context)
    if result["status"] == "no_language":
        await update.message.reply_text(messages.MSG_NO_ACTIVE_LANGUAGE_START)
        return
    if result["status"] == "no_questions":
        await update.message.reply_text(messages.MSG_NO_DIAGNOSTIC_QUESTIONS_FOR_LANG)
        return
    await update.message.reply_text(messages.MSG_START_DIAGNOSTICS)
    q_result = await diagnostics_flow.get_current_diagnostic_question(context)
    if q_result["status"] == "ok":
        await update.message.reply_text(q_result["text"], reply_markup=q_result["reply_markup"])
    elif q_result["status"] == "no_questions":
        await update.message.reply_text(messages.MSG_NO_DIAGNOSTIC_QUESTIONS_FOR_LANG)
    elif q_result["status"] == "done":
        await update.message.reply_text(messages.MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE)

async def handle_diagnostic_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        data_payload = query.data.replace(callback_data.DIAGNOSTIC_SCORE_PREFIX, "")
        question_id_str, score_str = data_payload.split('_')
        question_id = int(question_id_str)
        score = int(score_str)
    except Exception:
        await query.edit_message_text(messages.MSG_DIAGNOSTIC_SCORE_PARSE_ERROR)
        return
    context.user_data['telegram_id'] = update.effective_user.id
    result = await diagnostics_flow.process_diagnostic_score(context, question_id, score)
    if result["status"] == "next_question":
        q_result = await diagnostics_flow.get_current_diagnostic_question(context)
        if q_result["status"] == "ok":
            await query.edit_message_text(q_result["text"], reply_markup=q_result["reply_markup"])
        elif q_result["status"] == "no_questions":
            await query.edit_message_text(messages.MSG_NO_DIAGNOSTIC_QUESTIONS_FOR_LANG)
        elif q_result["status"] == "done":
            await query.edit_message_text(messages.MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE)
    elif result["status"] == "completed":
        await query.message.reply_text(messages.MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE)
        # Генерируем практику
        with get_session() as session:
            user = services.get_or_create_user(session, telegram_id=update.effective_user.id)
            user_progress = session.get(services.UserProgress, context.user_data.get('active_progress_id'))
            success, practice_result = await generate_practice_plan(context, session, user, user_progress)
            if success:
                await query.message.reply_text(messages.MSG_NEW_PRACTICE_QUESTIONS_READY.format(count=practice_result))
                # Здесь нужно вызвать функцию, которая покажет первый вопрос практики через practice_flow
                p_result = await practice_flow.get_current_practice_question(context)
                if p_result["status"] == "ok":
                    await query.message.reply_text(p_result["text"])
                else:
                    await query.message.reply_text(messages.MSG_PRACTICE_PLAN_FINISHED_INSTRUCTIONS)
            elif practice_result == "NO_QUESTIONS":
                await query.message.reply_text(messages.MSG_PRACTICE_PLAN_GENERATION_FAILED_NO_QUESTIONS)
            else:
                await query.message.reply_text(messages.MSG_PRACTICE_PLAN_GENERATION_ERROR)
    elif result["status"] == "no_active_question":
        await query.edit_message_text(messages.MSG_NO_ACTIVE_DIAGNOSTIC_QUESTION)

async def technology_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        technologies = services.list_languages(session)
        if not technologies:
            await update.message.reply_text(messages.MSG_NO_AVAILABLE_TECHNOLOGIES)
            return
        keyboard = [[InlineKeyboardButton(tech.name, callback_data=f"{callback_data.LANG_SELECT_PREFIX}{tech.id}")] for tech in technologies]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(messages.MSG_CHOOSE_TECHNOLOGY, reply_markup=reply_markup)

async def practice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    context.user_data['telegram_id'] = telegram_id
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        user_progress = services.get_or_create_user_progress(session, user_id=user.id, language_id=user.active_language_id)
        has_plan = services.user_has_practice_plan(session, user_progress_id=user_progress.id)
        if not has_plan:
            await update.message.reply_text(messages.MSG_NO_PRACTICE_PLAN)
            return
    q_result = await practice_flow.get_current_practice_question(context)
    if q_result["status"] == "ok":
        await update.message.reply_text(q_result["text"])
    else:
        await update.message.reply_text(messages.MSG_PRACTICE_PLAN_FINISHED_INSTRUCTIONS)

async def handle_next_question_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['telegram_id'] = query.from_user.id
    result = await practice_flow.next_practice_question(context)
    if result["status"] == "ok":
        q_result = await practice_flow.get_current_practice_question(context)
        if q_result["status"] == "ok":
            await query.edit_message_text(q_result["text"])
        else:
            await query.edit_message_text(messages.MSG_PRACTICE_PLAN_FINISHED_INSTRUCTIONS)
    else:
        await query.edit_message_text(messages.MSG_PRACTICE_PLAN_FINISHED_INSTRUCTIONS)

async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    language_slug = query.data.replace(callback_data.LANG_SELECT_PREFIX, "")
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=query.from_user.id)
        lang = services.get_language_by_id(session, int(language_slug))
        services.set_user_active_language(session, user_id=user.id, language_id=lang.id)
        await query.edit_message_text(f"Вы выбрали: {lang.name}\n\nЧтобы пройти диагностику, отправьте команду /diagnostics")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.message.from_user.id
    context.user_data['telegram_id'] = telegram_id
    with get_session() as session:
        user = services.get_or_create_user(session, telegram_id=telegram_id)
        state = get_user_state(session, telegram_id)
        if state in [UserState.PRACTICE.value, UserState.WAITING_FOR_ANSWER.value]:
            await update.message.reply_text(messages.MSG_THANKS_FOR_ANSWER_ANALYZING)
            answer_text = update.message.text
            result = await practice_flow.process_user_practice_answer(context, answer_text)
            if result["status"] == "continue":
                await update.message.reply_text(result["explanation"], reply_markup=result["reply_markup"])
            elif result["status"] == "finished":
                await update.message.reply_text(result["explanation"])
                for msg in result.get("finish_messages", []):
                    await update.message.reply_text(msg)
        else:
            await update.message.reply_text(messages.MSG_UNKNOWN_STATE)


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

def extract_json_from_llm_response(text):
    """Удаляет markdown-блоки и возвращает только JSON-строку."""
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()

async def _generate_and_save_practice_questions(context, session, user, user_progress):
    active_language = services.get_language_by_id(session, user.active_language_id)
    # Если результаты диагностики ещё не сохранены в JSON, вычислим их из ответов
    if not user_progress.diagnostic_scores_json:
        answers = services.get_diagnostic_answers_for_progress(session, user_progress_id=user_progress.id)
        if not answers:
            logger.error("Cannot generate practice plan: no diagnostic answers found.")
            return 0
        # Формируем словарь: category_id (str) -> последняя выставленная оценка
        scores_tmp = {}
        for ans in answers:
            # Нам нужен category_id вопроса. Получаем вопрос по id (кэшировать не обязательно)
            q = services.get_question_by_id(session, ans.question_id)
            if not q:
                continue
            scores_tmp[str(q.category_id)] = ans.score
        # Сохраняем в JSON, чтобы не вычислять повторно
        services.save_diagnostic_scores(session, user_progress_id=user_progress.id, scores=scores_tmp)
        diagnostic_scores = scores_tmp
    else:
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
