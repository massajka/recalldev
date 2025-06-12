from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from constants import messages
from src.bot.flow_result import FlowStatus, FlowResult
from telegram_rest_mvc.views import View
from src.bot.flows import practice as practice_flow
from src.db.db import get_session
from src.db import services
from langchain.schema import HumanMessage
import json
import logging
from constants import prompts

DEFAULT_ERR = getattr(messages, 'MSG_UNKNOWN_ERROR', 'Произошла ошибка, попробуйте снова.')
NO_PLAN_TEXT = getattr(messages, 'MSG_NO_PRACTICE_PLAN', 'У вас пока нет плана практики. Сначала пройдите диагностику.')

logger = logging.getLogger(__name__)

def render(result: FlowResult):
    dispatch = {
        FlowStatus.OK: _render_question,
        FlowStatus.CONTINUE: _render_continue,
        FlowStatus.FINISHED: _render_finished,
        FlowStatus.NO_PLAN: lambda _: (NO_PLAN_TEXT, None),
    }
    handler = dispatch.get(result.status, _render_error)
    return handler(result)


def _render_question(r: FlowResult):
    return r.get("text", DEFAULT_ERR), None


def _render_continue(r: FlowResult):
    return r.get("explanation", ""), r.get("reply_markup")


def _render_finished(r: FlowResult):
    text_lines = [r.get("explanation", "")]
    text_lines.extend(r.get("finish_messages", []))
    return "\n\n".join(filter(None, text_lines)), None


def _render_error(_: FlowResult):
    return DEFAULT_ERR, None


# ----------------- Helper functions previously in callbacks -----------------

async def _generate_and_save_practice_questions(context, session, user, user_progress):
    active_language = services.get_language_by_id(session, user.active_language_id)

    # Calculate diagnostic_scores if not saved
    if not user_progress.diagnostic_scores_json:
        answers = services.get_diagnostic_answers_for_progress(session, user_progress_id=user_progress.id)
        if not answers:
            logger.error("Cannot generate practice plan: no diagnostic answers found.")
            return 0
        scores_tmp = {}
        for ans in answers:
            q = services.get_question_by_id(session, ans.question_id)
            if not q:
                continue
            scores_tmp[str(q.category_id)] = ans.score
        services.save_diagnostic_scores(session, user_progress_id=user_progress.id, scores=scores_tmp)
        diagnostic_scores = scores_tmp
    else:
        diagnostic_scores = json.loads(user_progress.diagnostic_scores_json)

    all_categories = services.get_categories_for_language(session, language_id=active_language.id)
    category_map = {str(cat.id): cat.name for cat in all_categories}
    formatted_scores = "\n".join([
        f"- Категория '{category_map.get(cat_id, 'Unknown') }': Оценка {score}/5"
        for cat_id, score in diagnostic_scores.items()
    ])

    prompt_text = prompts.PRACTICE_PLAN_GENERATION_PROMPT_TEMPLATE.format(
        language_name=active_language.name,
        formatted_scores=formatted_scores,
        category_list_str=', '.join([cat.name for cat in all_categories])
    )

    llm = context.bot_data.get('chat_model')
    if not llm:
        logger.error("LLM (chat_model) not found in context.bot_data for practice plan generation.")
        return 0

    try:
        llm_raw = llm.invoke([HumanMessage(content=prompt_text)])
        llm_response = getattr(llm_raw, 'content', None)
        if not llm_response:
            logger.error("LLM returned no content for practice plan generation.")
            return 0
        plan_json_str = _extract_json_from_llm_response(llm_response)
        plan = json.loads(plan_json_str)
    except Exception as e:
        logger.error(f"Failed to generate practice plan via LLM: {e}")
        return 0

    questions = plan if isinstance(plan, list) else plan.get('questions')
    if not questions or not isinstance(questions, list):
        logger.error("LLM plan JSON invalid")
        return 0

    new_plan_items = 0
    first_new_item_id = None
    current_order_index = services.get_max_learning_plan_order_index(session, user_progress_id=user_progress.id) + 1

    for q in questions:
        category_name = q.get('category_name') or q.get('category')
        if not category_name:
            continue
        category = services.get_or_create_category(session, name=category_name)
        question_text = q.get('question_text') or q.get('text')
        if not question_text:
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
        if new_plan_items == 0:
            first_new_item_id = plan_item.id
        new_plan_items += 1
        current_order_index += 1

    if new_plan_items and first_new_item_id:
        services.set_current_learning_item(session, user_progress_id=user_progress.id, new_current_item_id=first_new_item_id)

    return new_plan_items


async def generate_practice_plan(context, session, user, user_progress):
    try:
        amount = await _generate_and_save_practice_questions(context, session, user, user_progress)
        if amount > 0:
            from src.bot.state_machine import set_user_state, UserState
            set_user_state(session, user.telegram_id, UserState.PRACTICE.value)
            return True, amount
        else:
            return False, "NO_QUESTIONS"
    except Exception as e:
        logger.error(f"Unexpected error in generate_practice_plan: {e}")
        return False, "ERROR"


class PracticeView(View):
    async def command(self):
        telegram_id = self.update.effective_user.id
        self.context.user_data['telegram_id'] = telegram_id

        with get_session() as session:
            user = services.get_or_create_user(session, telegram_id=telegram_id)
            user_progress = services.get_or_create_user_progress(
                session, user_id=user.id, language_id=user.active_language_id
            )
            if not services.user_has_practice_plan(session, user_progress_id=user_progress.id):
                await self.update.message.reply_text(messages.MSG_NO_PRACTICE_PLAN)
                return

        flow_res = await practice_flow.get_current_practice_question(self.context)
        text, markup = render(flow_res)
        await self.update.message.reply_text(text, reply_markup=markup)


class NextQuestionView(View):
    """Handle callback ACTION_NEXT_QUESTION to fetch next practice question."""

    async def command(self):
        query = self.update.callback_query
        await query.answer()

        self.context.user_data['telegram_id'] = query.from_user.id

        flow_res = await practice_flow.next_practice_question(self.context)

        if flow_res.status == FlowStatus.OK:
            q_res = await practice_flow.get_current_practice_question(self.context)
            q_text, _ = render(q_res)
            await query.edit_message_text(q_text)
        else:
            await query.edit_message_text(messages.MSG_PRACTICE_PLAN_FINISHED_INSTRUCTIONS)


# util moved from callbacks
import re

def _extract_json_from_llm_response(text: str) -> str:
    """Remove markdown blocks and return JSON string."""
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()
