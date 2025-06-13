import asyncio
import os
import sys


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging

from langchain.chat_models import ChatOpenAI
from telegram.ext import Application

from src.bot import urls as bot_urls
from src.db import services
from src.db.db import init_db
from src.settings import settings
from telegram_rest_mvc.registrar import register_routes


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- LLM Initialization ---
if not settings.OPENAI_API_KEY:
    logger.warning(
        "OPENAI_API_KEY not found in settings! LLM features will not work. Setting llm to None."
    )
    llm = None
else:
    try:
        logger.info(f"OPENAI_API_KEY in settings: {settings.OPENAI_API_KEY!r}")
        llm = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            temperature=0.7,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        logger.info(f"ChatOpenAI initialized successfully: {llm}")
    except Exception as e:
        logger.exception("Failed to initialize ChatOpenAI. LLM features will not work.")
        llm = None

# --- Main Application Setup ---
if __name__ == "__main__":
    logger.info("Starting bot...")
    init_db()
    logger.info("Database initialized.")

    if len(sys.argv) > 1 and sys.argv[1] == "recreatedb":
        import scripts.drop_db

        scripts.drop_db.drop_database()
        import scripts.create_db

        scripts.create_db.create_and_populate_database()

    services.try_populate_initial_data()
    logger.info("Initial data population attempt complete.")

    if not settings.TELEGRAM_TOKEN:
        logger.critical("TELEGRAM_TOKEN not found in settings!")
        exit(1)
    if llm is None:
        logger.warning(
            "LLM (ChatOpenAI) is not available (likely missing OPENAI_API_KEY or initialization failed). LLM-dependent features will be disabled."
        )

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app = Application.builder().token(settings.TELEGRAM_TOKEN).build()
    app.bot_data["chat_model"] = llm
    logger.info(f"[Startup] llm in bot_data: {app.bot_data.get('chat_model')!r}")
    if llm is None:
        logger.warning(
            "[Startup] llm is None at runtime! LLM-dependent features will not work."
        )
    register_routes(app, bot_urls.router)
    logger.info("Bot is running...")
    app.run_polling()
