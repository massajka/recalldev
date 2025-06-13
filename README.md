# RecallDev Telegram Bot

![coverage](./coverage-badge.svg)

RecallDev Bot is a Telegram bot designed to help users learn programming languages. It features an automated flow: language selection triggers diagnostics, followed by AI-generated personalized practice plans. Users can then practice questions from their plan and receive AI-powered feedback on their answers.

## Prerequisites

*   Python 3.8+
*   Pip (Python package installer)
*   Git (optional, for cloning)

## Setup

1.  **Clone the repository (optional):**
    ```bash
    git clone <your_repository_url>
    cd recalldev
    ```
    If you have the files directly, navigate to the project directory `c:\Users\Admin\Projects\recalldev`.

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    ```
    Activate it:
    *   Windows: `venv\Scripts\activate`
    *   macOS/Linux: `source venv/bin/activate`

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a `.env` file in the root of the project directory (`c:\Users\Admin\Projects\recalldev`) with the following variables. **Names must match exactly as shown below (double underscores for section nesting):**

    | Variable Name              | Required | Description                                   |
    |---------------------------|----------|-----------------------------------------------|
    | TELEGRAM__TOKEN           | Yes      | Telegram Bot Token                            |
    | LLM__OPENAI_API_KEY       | Yes      | OpenAI API Key for GPT                        |
    | DATABASE__NAME            | No       | Database file name (default: db.sqlite3)      |
    | DATABASE__ENGINE          | No       | Database engine (sqlite/postgresql, default: sqlite) |
    | DATABASE__USER            | No       | DB user (for PostgreSQL)                      |
    | DATABASE__PASSWORD        | No       | DB password (for PostgreSQL)                  |
    | DATABASE__HOST            | No       | DB host (for PostgreSQL, default: localhost)  |
    | DATABASE__PORT            | No       | DB port (for PostgreSQL, default: 5432)       |
    | DEBUG                     | No       | Set to true for debug mode                    |

    Example `.env`:
    ```env
    TELEGRAM__TOKEN=123456:ABC-Your-Telegram-Token
    LLM__OPENAI_API_KEY=sk-Your-OpenAI-Key
    # DATABASE__NAME=recall_dev.db
    # DATABASE__ENGINE=sqlite
    # DEBUG=true
    ```
    
    - All variables are loaded via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/), with double underscores (`__`) as section delimiters.
    - Do **not** use single underscore or legacy names like `TELEGRAM_TOKEN` or `OPENAI_API_KEY` — they will be ignored by the config loader.
    ```
    Replace `YOUR_TELEGRAM_BOT_TOKEN` with your actual Telegram Bot token and `YOUR_OPENAI_API_KEY` with your OpenAI API key.

5.  **Initialize and populate the database:**
    The database schema is defined using SQLModel. The `init_db()` function (called in `main.py` on startup) ensures the database and its tables are created if they don't exist.
    The `services.try_populate_initial_data()` function (also called in `main.py` on startup) attempts to populate the database with initial languages, categories, and questions from `initial_data.json` if the database is empty.

    Running the bot (`python main.py`) will handle the database creation and initial data population automatically. There is no separate script to run for this.

## Running the Bot

1.  **Ensure your virtual environment is activated.**
2.  **Navigate to the project directory:**
    ```bash
    cd c:\Users\Admin\Projects\recalldev
    ```
3.  **Run the main application:**
    ```bash
    python main.py
    ```

The bot should now be running and responsive on Telegram.

## Architecture Overview

The codebase follows a strict MVC + State-Machine pattern:

| Layer | Folder | Responsibility |
|-------|--------|----------------|
| **Controllers** | `src/bot/callbacks.py` | Receive Telegram updates, invoke flow functions, render results via views, send messages. **No business logic.** |
| **Flows** | `src/bot/flows/` | Pure business logic. Never import Telegram API. Return `FlowResult` objects that contain a `FlowStatus` enum and optional data. |
| **Views** | `src/bot/views/` | Convert `FlowResult` to `(text, reply_markup)` tuples. Contain all message templates / keyboards. |
| **State Machine** | `src/bot/state_machine.py` | Tracks the user’s current state (`IDLE`, `DIAGNOSTICS`, `PRACTICE`, `WAITING_FOR_ANSWER`).  |
| **Models / DB** | `src/db/*` | SQLModel ORM models & helpers. |

```
┌───────────┐   FlowResult   ┌────────┐   render   ┌─────────┐
│ callbacks │──────────────▶│ flows  │────────────▶│  views  │
└───────────┘                └────────┘            └─────────┘
   ▲  │ send                                    │ send
   │  └────────────── Telegram API ─────────────┘
```

### FlowResult / FlowStatus

```python
from enum import StrEnum

class FlowStatus(StrEnum):
    OK = "ok"
    NEXT_QUESTION = "next_question"
    COMPLETED = "completed"  # diagnostics finished
    CONTINUE = "continue"    # practice answer saved, show explanation
    FINISHED = "finished"    # no more practice questions
    ...

@dataclass
class FlowResult:
    status: FlowStatus
    data:   dict | None = None
```

Flows return only `FlowResult`, keeping them **pure and testable**.

### State Machine

| State | Meaning |
|-------|---------|
| `IDLE` | User just started / no active flow |
| `DIAGNOSTICS` | User is answering diagnostic questions |
| `PRACTICE` | User is working through practice plan |
| `WAITING_FOR_ANSWER` | Bot is waiting for text answer to a practice question |

Transitions are handled centrally in `state_machine.py` and updated in controllers.

## Bot Flow (short)

1. **/start** → language list.
2. **Language selected** → diagnostics auto-start.
3. **Diagnostics completed** → practice plan auto-generated.
4. **/practice** → next practice question.
5. **User answers** → LLM feedback → *Next question*.
6. Loop until plan finished → congrats.

Detailed sequence is in `docs/bot_flow_en.md`.

## Contributing

1. Keep functions small and side-effect-free where possible.
2. All new flows must **never** call Telegram API directly — return `FlowResult`.
3. Avoid bulky `if/else`; prefer enums + dispatch tables.
4. Add/adjust unit tests under `tests/` (not yet included).  
5. Run `ruff` / `black` before committing.
