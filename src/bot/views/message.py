"""View handling plain user text answers during practice."""

from constants import messages
from src.bot.flows import practice as practice_flow
from src.bot.state_machine import UserState, get_user_state
from src.bot.views.practice import render
from src.db import services
from src.db.db import get_session
from telegram_rest_mvc.views import View


class UserTextMessageView(View):
    async def command(self):
        telegram_id = self.update.message.from_user.id
        self.context.user_data["telegram_id"] = telegram_id
        with get_session() as session:
            user = services.get_or_create_user(session, telegram_id=telegram_id)
            state = get_user_state(session, telegram_id)
            if state in [UserState.PRACTICE.value, UserState.WAITING_FOR_ANSWER.value]:
                await self.update.message.reply_text(
                    messages.MSG_THANKS_FOR_ANSWER_ANALYZING
                )
                answer_text = self.update.message.text
                p_res = await practice_flow.process_user_practice_answer(
                    self.context, answer_text
                )
                text, markup = render(p_res)
                await self.update.message.reply_text(text, reply_markup=markup)
            else:
                await self.update.message.reply_text(messages.MSG_UNKNOWN_STATE)
