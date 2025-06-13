import asyncio
import os
import sys


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging

from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from telegram.ext import Application

from src.bot import urls as bot_urls
from src.db import services
from src.db.db import init_db
from telegram_rest_mvc.registrar import register_routes


load_dotenv()

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- LLM Initialization ---
# ChatOpenAI будет автоматически искать OPENAI_API_KEY в переменных окружения, если он не передан явно.
# load_dotenv() уже вызван в начале файла.
llm_api_key = os.getenv("OPENAI_API_KEY")
if not llm_api_key:
    logger.warning(
        "OPENAI_API_KEY not found in environment variables! LLM features will not work. Setting llm to None."
    )
    llm = None
else:
    try:
        llm = ChatOpenAI(
            model_name="gpt-3.5-turbo", temperature=0.7, openai_api_key=llm_api_key
        )
        logger.info("ChatOpenAI initialized successfully.")
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

    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        logger.critical("TELEGRAM_TOKEN not found in environment variables!")
        exit(1)
    if llm is None:  # Проверяем, был ли LLM успешно инициализирован
        logger.warning(
            "LLM (ChatOpenAI) is not available (likely missing OPENAI_API_KEY or initialization failed). LLM-dependent features will be disabled."
        )

    app = Application.builder().token(TOKEN).build()

    # Store LLM instance in bot_data for access in handlers (единственный ключ)
    app.bot_data["chat_model"] = llm

    # Register telegram_rest_mvc routes
    register_routes(app, bot_urls.router)

    logger.info("Bot is running...")
    app.run_polling()
