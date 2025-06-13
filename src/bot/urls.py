"""URL configuration for telegram_rest_mvc routes used by this bot."""

from constants.callback_data import (
    ACTION_NEXT_QUESTION,
    DIAGNOSTIC_SCORE_PREFIX,
    LANG_SELECT_PREFIX,
)
from src.bot.views import diagnostics as diagnostics_view_module
from src.bot.views import language as language_view_module
from src.bot.views import message as message_view_module
from src.bot.views import practice as practice_view_module
from src.bot.views import technology as technology_view_module
from telegram_rest_mvc.router import Router
from telegram_rest_mvc.router import callback as cb_path
from telegram_rest_mvc.router import message as msg_path
from telegram_rest_mvc.router import path
from telegram_rest_mvc.views import View


router = Router()


class PingView(View):
    async def command(self):
        await self.update.message.reply_text("pong")


class StartView(View):
    async def command(self):
        # Delegate to TechnologyView to ask user select technology/language
        await technology_view_module.TechnologyView(self.update, self.context).command()


# Register routes
path(router, "/ping", PingView.as_handler(), name="ping")
path(router, "/start", StartView.as_handler(), name="start")
path(
    router,
    "/diagnostics",
    diagnostics_view_module.DiagnosticsView.as_handler(),
    name="diagnostics",
)
path(
    router, "/practice", practice_view_module.PracticeView.as_handler(), name="practice"
)
path(
    router,
    "/technology",
    technology_view_module.TechnologyView.as_handler(),
    name="technology",
)

# Text messages
msg_path(router, message_view_module.UserTextMessageView.as_handler(), name="user_text")

# Callback route for diagnostic scores
cb_path(
    router,
    pattern=f"^{DIAGNOSTIC_SCORE_PREFIX}",
    handler=diagnostics_view_module.DiagnosticScoreView.as_handler(),
    name="diagnostic_score",
)

# Language selection callback
cb_path(
    router,
    pattern=f"^{LANG_SELECT_PREFIX}",
    handler=language_view_module.LanguageSelectionView.as_handler(),
    name="language_select",
)

# Next practice question
cb_path(
    router,
    pattern=f"^{ACTION_NEXT_QUESTION}$",
    handler=practice_view_module.NextQuestionView.as_handler(),
    name="next_question",
)
