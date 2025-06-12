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
from src.bot.views import diagnostics as diagnostics_view, practice as practice_view
from src.bot.flow_result import FlowStatus

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
    flow_result = await diagnostics_flow.start_diagnostics(context)
    text, markup = diagnostics_view.render(flow_result)
    await update.message.reply_text(text, reply_markup=markup)

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
    flow_result = await diagnostics_flow.process_diagnostic_score(context, question_id, score)
    if flow_result.status in (FlowStatus.NEXT_QUESTION, FlowStatus.OK):
        q_res = await diagnostics_flow.get_current_diagnostic_question(context)
        q_text, q_markup = diagnostics_view.render(q_res)
        await query.edit_message_text(q_text, reply_markup=q_markup)
    elif flow_result.status in (FlowStatus.COMPLETED, FlowStatus.DONE):
        await query.message.reply_text(messages.MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE)
        # Generate practice
        with get_session() as session:
            user = services.get_or_create_user(session, telegram_id=update.effective_user.id)
            user_progress = session.get(services.UserProgress, context.user_data.get('active_progress_id'))
            success, practice_result = await generate_practice_plan(context, session, user, user_progress)
            if success:
                await query.message.reply_text(messages.MSG_NEW_PRACTICE_QUESTIONS_READY.format(count=practice_result))
                # Show the first practice question
                p_result = await practice_flow.get_current_practice_question(context)
                p_text, p_markup = practice_view.render(p_result)
                await query.message.reply_text(p_text, reply_markup=p_markup)
            elif practice_result == "NO_QUESTIONS":
                await query.message.reply_text(messages.MSG_PRACTICE_PLAN_GENERATION_FAILED_NO_QUESTIONS)
            else:
                await query.message.reply_text(messages.MSG_PRACTICE_PLAN_GENERATION_ERROR)
    elif flow_result.status == FlowStatus.NO_ACTIVE_QUESTION:
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
        if not services.user_has_practice_plan(session, user_progress_id=user_progress.id):
            await update.message.reply_text(messages.MSG_NO_PRACTICE_PLAN)
            return
    flow_res = await practice_flow.get_current_practice_question(context)
    text, markup = practice_view.render(flow_res)
    await update.message.reply_text(text, reply_markup=markup)

async def handle_next_question_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['telegram_id'] = query.from_user.id
    flow_res = await practice_flow.next_practice_question(context)
    if flow_res.status == FlowStatus.OK:
        q_res = await practice_flow.get_current_practice_question(context)
        q_text, _ = practice_view.render(q_res)
        await query.edit_message_text(q_text)
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
            p_res = await practice_flow.process_user_practice_answer(context, answer_text)
            text, markup = practice_view.render(p_res)
            await update.message.reply_text(text, reply_markup=markup)
        else:
            await update.message.reply_text(messages.MSG_UNKNOWN_STATE)


async def edit_message(query, text):
    # Universal edit_message_text for callback_query
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
    # Universal reply_text for message/callback_query
    if hasattr(update, "message") and update.message:
        await update.message.reply_text(message)
    elif hasattr(update, "callback_query") and update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(message)
    else:
        logger.warning(f"Failed to send message: {message}")

def extract_json_from_llm_response(text):
    """Remove markdown blocks and return only JSON string."""
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()

async def _generate_and_save_practice_questions(context, session, user, user_progress):
    active_language = services.get_language_by_id(session, user.active_language_id)
    # If the results of the diagnosis are not saved in JSON, calculate them from the answers
    if not user_progress.diagnostic_scores_json:
        answers = services.get_diagnostic_answers_for_progress(session, user_progress_id=user_progress.id)
        if not answers:
            logger.error("Cannot generate practice plan: no diagnostic answers found.")
            return 0
        # Form a dictionary: category_id (str) -> last given score
        scores_tmp = {}
        for ans in answers:
            # We need the category_id of the question. Get the question by id (no need to cache)
            q = services.get_question_by_id(session, ans.question_id)
            if not q:
                continue
            scores_tmp[str(q.category_id)] = ans.score
        # Save in JSON, so we don't calculate again
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
        # Find or create question in the database by text and category
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
