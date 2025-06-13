from typing import Any, Awaitable, Callable, Coroutine

from telegram import Update
from telegram.ext import ContextTypes


class View:
    """Base View: instance stores `update` & `context`; override `command()`.

    For backward compatibility, subclasses can still set `command_handler` attribute.
    """

    # legacy support
    command_handler: (
        Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]] | None
    ) = None

    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.update = update
        self.context = context

    async def command(self):  # noqa: D401
        """Handle command (override in subclass)."""
        if self.command_handler:
            # call legacy handler if defined as attribute
            await self.command_handler(self.update, self.context)
        else:
            raise NotImplementedError(
                "View must implement command() or set command_handler"
            )

    @classmethod
    def as_handler(
        cls,
    ) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        async def _handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            self = cls(update, context)
            await self.command()

        return _handler
