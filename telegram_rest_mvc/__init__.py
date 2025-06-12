"""Minimal REST-style MVC framework helpers for Telegram bots.

This package provides:
    • Router / path() — URL-like routing for Telegram updates.
    • Base View classes with Django-style dispatch.
    • Helpers to convert routes into python-telegram-bot handlers.

Usage example::

    from telegram_rest_mvc import Router, path
    from myapp import views

    router = Router()
    path(router, '/start', views.StartView.as_handler(), name='start')

    application = ApplicationBuilder().token(TOKEN).build()
    register_routes(application, router)

"""
