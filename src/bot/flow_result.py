from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional

class FlowStatus(str, Enum):
    """Унифицированный список статусов для результатов flow-функций."""

    OK = "ok"
    NO_LANGUAGE = "no_language"
    NO_QUESTIONS = "no_questions"
    NEXT_QUESTION = "next_question"
    COMPLETED = "completed"
    DONE = "done"
    NO_ACTIVE_QUESTION = "no_active_question"
    ERROR = "error"
    CONTINUE = "continue"
    FINISHED = "finished"
    NO_PLAN = "no_plan"


@dataclass(slots=True)
class FlowResult:
    """Result of flow function execution.

    status: FlowStatus       — final execution result
    data:   Optional[dict]   — arbitrary data (text, reply_markup and so on)
    """

    status: FlowStatus
    data: Optional[dict] = None

    def get(self, key: str, default: Any = None) -> Any:  # удобный доступ
        return self.data.get(key, default) if self.data else default
