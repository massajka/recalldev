from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class Route:
    pattern: str  # e.g. "/start" or "callback:ACTION_NEXT"
    handler: Callable
    name: Optional[str] = None
    kind: str = "command"  # 'command' or 'callback' or 'message'


class Router:
    """Simple registry that stores routes and resolves by pattern."""

    def __init__(self):
        self._routes: List[Route] = []

    def add(
        self,
        pattern: str,
        handler: Callable,
        name: Optional[str] = None,
        kind: str = "command",
    ):
        self._routes.append(Route(pattern, handler, name, kind))

    def all_routes(self) -> List[Route]:
        return list(self._routes)


def path(router: "Router", pattern: str, handler: Callable, name: Optional[str] = None):
    """Django-like helper to register a route on the given router."""
    router.add(pattern, handler, name, kind="command")
    return handler


def callback(
    router: "Router", pattern: str, handler: Callable, name: Optional[str] = None
):
    """Register a CallbackQuery pattern route."""
    router.add(pattern, handler, name, kind="callback")
    return handler


def message(router: "Router", handler: Callable, name: Optional[str] = None):
    """Register a plain text message handler."""
    router.add("__message__", handler, name, kind="message")
    return handler
