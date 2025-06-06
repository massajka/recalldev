# RecallDev Telegram Bot

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
    Create a `.env` file in the root of the project directory (`c:\Users\Admin\Projects\recalldev`) with the following content:
    ```env
    TELEGRAM_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
    # DATABASE_URL="sqlite:///./recall_dev.db" # Optional, default is recall_dev.db in project root
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
