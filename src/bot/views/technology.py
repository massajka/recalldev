"""View that shows user a list of available technologies to choose from."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from constants import callback_data, messages
from src.db import services
from src.db.db import get_session
from telegram_rest_mvc.views import View


class TechnologyView(View):
    async def command(self):
        telegram_id = self.update.effective_user.id
        with get_session() as session:
            user = services.get_or_create_user(session, telegram_id=telegram_id)
            technologies = services.list_languages(session)
            if not technologies:
                await self.update.message.reply_text(
                    messages.MSG_NO_AVAILABLE_TECHNOLOGIES
                )
                return
            keyboard = [
                [
                    InlineKeyboardButton(
                        tech.name,
                        callback_data=f"{callback_data.LANG_SELECT_PREFIX}{tech.id}",
                    )
                ]
                for tech in technologies
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await self.update.message.reply_text(
                messages.MSG_CHOOSE_TECHNOLOGY, reply_markup=reply_markup
            )
