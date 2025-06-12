from telegram import InlineKeyboardMarkup
from constants import messages
from src.bot.flow_result import FlowStatus, FlowResult

DEFAULT_ERR = getattr(messages, 'MSG_UNKNOWN_ERROR', 'Произошла ошибка, попробуйте снова.')

def render(result: FlowResult):
    dispatch = {
        FlowStatus.OK: _render_question,
        FlowStatus.CONTINUE: _render_continue,
        FlowStatus.FINISHED: _render_finished,
        FlowStatus.NO_PLAN: lambda _: (messages.MSG_NO_PRACTICE_PLAN, None),
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
