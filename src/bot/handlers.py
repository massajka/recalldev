import logging
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from src.bot import callbacks
from constants.callback_data import LANG_SELECT_PREFIX, DIAGNOSTIC_SCORE_PREFIX, ACTION_NEXT_QUESTION

logger = logging.getLogger(__name__)

# ACTION_DISCUSS_ANSWER is available in constants.callback_data if needed elsewhere

def register_all_handlers(app: Application):
    """Registers all command, callback, and message handlers with the application."""

    # Command Handlers
    app.add_handler(CommandHandler("start", callbacks.start_command))
    app.add_handler(CommandHandler("language", callbacks.language_command))
    app.add_handler(CommandHandler("diagnostics", callbacks.diagnostics_command))
    app.add_handler(CommandHandler("practice", callbacks.practice_command))
    logger.info("Command handlers registered.")

    # Callback Query Handlers
    # Note: The pattern for callback query handlers should be specific enough.
    # Using f"^{PREFIX_CONSTANT}" matches anything starting with the prefix.
    # Using f"^{PREFIX_CONSTANT}$" would match only the prefix itself (if no other data is appended).
    # For prefixes that are followed by data (e.g., item IDs, scores), f"^{PREFIX_CONSTANT}" is appropriate.
    # For actions that are standalone, f"^{ACTION_CONSTANT}$" is appropriate.

    app.add_handler(CallbackQueryHandler(callbacks.handle_language_selection, pattern=f"^{LANG_SELECT_PREFIX}"))
    app.add_handler(CallbackQueryHandler(callbacks.handle_diagnostic_score, pattern=f"^{DIAGNOSTIC_SCORE_PREFIX}"))
    app.add_handler(CallbackQueryHandler(callbacks.handle_next_question_callback, pattern=f"^{ACTION_NEXT_QUESTION}$")) # Exact match for this action
    # app.add_handler(CallbackQueryHandler(callbacks.handle_discuss_answer_callback, pattern=f"^{ACTION_DISCUSS_ANSWER}_")) # Feature commented out
    logger.info("Callback query handlers registered.")

    # Message Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callbacks.handle_text_message))
    logger.info("Message handlers registered.")

    logger.info("All handlers registered successfully.")
