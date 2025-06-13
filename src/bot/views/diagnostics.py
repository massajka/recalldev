import logging

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from constants import callback_data, messages
from src import utils
from src.bot.flow_result import FlowResult, FlowStatus
from src.bot.flows import diagnostics as diagnostics_flow
from src.bot.flows import practice as practice_flow
from src.bot.views import practice as practice_view
from src.db import services
from src.db.db import get_session
from telegram_rest_mvc.views import View


logger = logging.getLogger(__name__)

DEFAULT_ERR = getattr(
    messages, "MSG_UNKNOWN_ERROR", "Произошла ошибка, попробуйте снова."
)


def render(result: FlowResult):
    """Convert FlowResult diagnostics to text/markup for Telegram."""
    dispatch = {
        FlowStatus.OK: _render_question,
        FlowStatus.NO_LANGUAGE: lambda _: (messages.MSG_NO_ACTIVE_LANGUAGE_START, None),
        FlowStatus.NO_QUESTIONS: lambda _: (
            messages.MSG_NO_DIAGNOSTIC_QUESTIONS_FOR_LANG,
            None,
        ),
        FlowStatus.DONE: lambda _: (
            messages.MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE,
            None,
        ),
        FlowStatus.COMPLETED: lambda _: (
            messages.MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE,
            None,
        ),
        FlowStatus.NEXT_QUESTION: _render_question,
    }
    handler = dispatch.get(result.status, _render_error)

    return handler(result)


class DiagnosticsView(View):
    async def command(self):
        telegram_id = self.update.effective_user.id
        self.context.user_data["telegram_id"] = telegram_id

        flow_result = await diagnostics_flow.start_diagnostics(self.context)

        # If user has no active language, send technology selection list
        if flow_result.status == FlowStatus.NO_LANGUAGE:
            from src.bot.views.technology import TechnologyView

            await TechnologyView(self.update, self.context).command()
            return

        text, markup = render(flow_result)
        msg = utils.get_effective_message(self.update, self.context)
        if msg:
            await msg.reply_text(text, reply_markup=markup)
        else:
            logger.error("No message object available to reply to in DiagnosticsView.")


def _render_question(result: FlowResult):
    text = result.get("text", DEFAULT_ERR)
    reply_markup: InlineKeyboardMarkup | None = result.get("reply_markup")

    return text, reply_markup


def _render_error(_: FlowResult):
    return DEFAULT_ERR, None


class DiagnosticScoreView(View):
    """Handle callback query with diagnostic score selection (formerly handle_diagnostic_score)."""

    async def command(self):
        from constants import messages
        from src.bot.views import diagnostics as diagnostics_view  # same module, safe
        from src.bot.views.practice import (
            generate_practice_plan,  # imported from new helpers
        )

        query = self.update.callback_query
        await query.answer()

        logger.info(f"DiagnosticScoreView received data: {query.data}")

        try:
            data_payload = query.data.replace(callback_data.DIAGNOSTIC_SCORE_PREFIX, "")
            question_id_str, score_str = data_payload.split("_")
            question_id = int(question_id_str)
            score = int(score_str)
        except Exception:
            await query.edit_message_text(messages.MSG_DIAGNOSTIC_SCORE_PARSE_ERROR)
            return

        self.context.user_data["telegram_id"] = self.update.effective_user.id

        flow_result = await diagnostics_flow.process_diagnostic_score(
            self.context, question_id, score
        )

        if flow_result.status in (FlowStatus.NEXT_QUESTION, FlowStatus.OK):
            q_res = await diagnostics_flow.get_current_diagnostic_question(self.context)
            q_text, q_markup = diagnostics_view.render(q_res)
            await query.edit_message_text(q_text, reply_markup=q_markup)
            return

        if flow_result.status in (FlowStatus.COMPLETED, FlowStatus.DONE):
            await query.message.reply_text(
                messages.MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE
            )

            # Generate practice plan
            with get_session() as session:
                user = services.get_or_create_user(
                    session, telegram_id=self.update.effective_user.id
                )
                user_progress = session.get(
                    services.UserProgress,
                    self.context.user_data.get("active_progress_id"),
                )

                success, practice_result = await generate_practice_plan(
                    self.context, session, user, user_progress
                )

            if success:
                await query.message.reply_text(
                    messages.MSG_NEW_PRACTICE_QUESTIONS_READY.format(
                        count=practice_result
                    )
                )
                # First practice question
                p_res = await practice_flow.get_current_practice_question(self.context)
                p_text, p_markup = practice_view.render(p_res)
                await query.message.reply_text(p_text, reply_markup=p_markup)
            elif practice_result == "NO_QUESTIONS":
                await query.message.reply_text(
                    messages.MSG_PRACTICE_PLAN_GENERATION_FAILED_NO_QUESTIONS
                )
            else:
                await query.message.reply_text(
                    messages.MSG_PRACTICE_PLAN_GENERATION_ERROR
                )
            return

        if flow_result.status == FlowStatus.NO_ACTIVE_QUESTION:
            await query.edit_message_text(messages.MSG_NO_ACTIVE_DIAGNOSTIC_QUESTION)
            return
