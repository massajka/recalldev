"""View to handle language selection inline-button callback."""
from telegram_rest_mvc.views import View
from telegram import Update
from telegram.ext import ContextTypes
from constants import callback_data
from src.db.db import get_session
from src.db import services

class LanguageSelectionView(View):
    async def command(self):
        query = self.update.callback_query
        await query.answer()
        language_slug = query.data.replace(callback_data.LANG_SELECT_PREFIX, "")
        with get_session() as session:
            user = services.get_or_create_user(session, telegram_id=query.from_user.id)
            lang = services.get_language_by_id(session, int(language_slug))
            services.set_user_active_language(session, user_id=user.id, language_id=lang.id)
            await query.edit_message_text(
                f"Вы выбрали: {lang.name}\n\nЧтобы пройти диагностику, отправьте команду /diagnostics"
            )
