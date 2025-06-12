"""Utilities to register telegram_rest_mvc routes to python-telegram-bot Application."""
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from .router import Router


def register_routes(app: Application, router: Router):
    for route in router.all_routes():
        if route.kind == "command":
            app.add_handler(CommandHandler(route.pattern.lstrip('/'), route.handler))
        elif route.kind == "callback":
            app.add_handler(CallbackQueryHandler(route.handler, pattern=route.pattern))
        elif route.kind == "message":
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route.handler))
        # Extend here for messages, etc.
