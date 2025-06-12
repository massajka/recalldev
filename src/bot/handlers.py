from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from src.bot import callbacks
from constants.callback_data import LANG_SELECT_PREFIX, DIAGNOSTIC_SCORE_PREFIX, ACTION_NEXT_QUESTION

def register_all_handlers(app: Application):
    app.add_handler(CommandHandler("start", callbacks.start_command))
    app.add_handler(CommandHandler("diagnostics", callbacks.diagnostics_command))
    app.add_handler(CommandHandler("practice", callbacks.practice_command))
    app.add_handler(CommandHandler("technology", callbacks.technology_command))
    app.add_handler(CallbackQueryHandler(callbacks.handle_language_selection, pattern=f"^{LANG_SELECT_PREFIX}"))
    app.add_handler(CallbackQueryHandler(callbacks.handle_diagnostic_score, pattern=f"^{DIAGNOSTIC_SCORE_PREFIX}"))
    app.add_handler(CallbackQueryHandler(callbacks.handle_next_question_callback, pattern=f"^{ACTION_NEXT_QUESTION}$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callbacks.handle_text_message))
