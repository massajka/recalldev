from src.bot.views import diagnostics as view
from src.bot.flow_result import FlowResult, FlowStatus


def test_render_ok():
    fr = FlowResult(FlowStatus.OK, {"text": "T", "reply_markup": None})
    text, rm = view.render(fr)
    assert text == "T"
    assert rm is None


def test_render_no_language():
    fr = FlowResult(FlowStatus.NO_LANGUAGE)
    text, _ = view.render(fr)
    assert "язык" in text.lower()


def test_render_unknown_status():
    fr = FlowResult(FlowStatus.ERROR)
    text, _ = view.render(fr)
    # DEFAULT_ERR fallback used
    assert "ошибка" in text.lower()
