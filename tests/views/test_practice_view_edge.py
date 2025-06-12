from src.bot.views import practice as view
from src.bot.flow_result import FlowResult, FlowStatus


def test_no_plan():
    text, _ = view.render(FlowResult(FlowStatus.NO_PLAN))
    assert "план" in text.lower()
