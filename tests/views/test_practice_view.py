from src.bot.views import practice as view
from src.bot.flow_result import FlowResult, FlowStatus
from telegram import InlineKeyboardMarkup, InlineKeyboardButton


def mk_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Next", callback_data="x")]])


def test_question():
    fr = FlowResult(FlowStatus.OK, {"text": "Q"})
    text, rm = view.render(fr)
    assert text == "Q" and rm is None


def test_continue():
    fr = FlowResult(FlowStatus.CONTINUE, {"explanation": "E", "reply_markup": mk_btn()})
    text, rm = view.render(fr)
    assert "E" in text and isinstance(rm, InlineKeyboardMarkup)


def test_finished():
    fr = FlowResult(FlowStatus.FINISHED, {"explanation": "E", "finish_messages": ["Done"]})
    text, rm = view.render(fr)
    assert "Done" in text and rm is None
