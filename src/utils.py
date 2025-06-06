import re

def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы MarkdownV2 для Telegram."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
