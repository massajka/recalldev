from src.settings.config import CONFIG


# Standard settings for the application
DATABASE_URL = CONFIG.database.build_url()
# All individual DB params are available via CONFIG.database.<field> (engine, name, user, password, host, port, url)
TELEGRAM_TOKEN = CONFIG.telegram.token
OPENAI_API_KEY = CONFIG.llm.openai_api_key
DEBUG = CONFIG.debug

# --- User custom settings below ---
# You can add your own environment variables to .env,
# and access them through CONFIG.<your_section>.<your_var>
