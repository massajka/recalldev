from telegram import InlineKeyboardMarkup
from constants import messages
from src.bot.flow_result import FlowStatus, FlowResult

DEFAULT_ERR = getattr(messages, 'MSG_UNKNOWN_ERROR', 'Произошла ошибка, попробуйте снова.')


def render(result: FlowResult):
    """Convert FlowResult diagnostics to text/markup for Telegram."""
    dispatch = {
        FlowStatus.OK: _render_question,
        FlowStatus.NO_LANGUAGE: lambda _: (messages.MSG_NO_ACTIVE_LANGUAGE_START, None),
        FlowStatus.NO_QUESTIONS: lambda _: (messages.MSG_NO_DIAGNOSTIC_QUESTIONS_FOR_LANG, None),
        FlowStatus.DONE: lambda _: (messages.MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE, None),
        FlowStatus.COMPLETED: lambda _: (messages.MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE, None),
        FlowStatus.NEXT_QUESTION: _render_question,
    }
    handler = dispatch.get(result.status, _render_error)

    return handler(result)


def _render_question(result: FlowResult):
    text = result.get("text", DEFAULT_ERR)
    reply_markup: InlineKeyboardMarkup | None = result.get("reply_markup")
    return text, reply_markup


def _render_error(_: FlowResult):
    return DEFAULT_ERR, None
