import re


def get_effective_message(update, context):
    """
    Returns the 'active' message object for the current view:
    - update.message (обычные сообщения)
    - context.user_data['message'] (если был callback_query и message был передан)
    """
    msg = getattr(update, "message", None)
    if msg:
        return msg
    return getattr(context, "user_data", {}).get("message")


def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы MarkdownV2 для Telegram."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)
