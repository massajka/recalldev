# Bot Flow Description

*   **Step 1: User starts the bot (`/start` or `/language`)**
    *   The bot offers to select a programming language if an active language is not yet set.
*   **Step 2: User selects a language**
    *   The bot confirms the selection and announces the automatic start of diagnostics.
    *   If diagnostics have already been completed, it informs the user.
    *   It loads diagnostic questions, sets the first one as current, and sends it.
*   **Step 3: Bot sends a diagnostic question, user answers (rates their knowledge on a scale of 1 to 5)**
    *   The user clicks a button with their score.
    *   The bot saves the score, confirms its receipt, and sends the next diagnostic question.
    *   If there are no more diagnostic questions:
        *   It saves all scores.
        *   Automatically generates a personalized practice plan using an LLM based on diagnostic results.
        *   Informs the user that the plan is ready and suggests using the `/practice` command.
*   **Step 4: User requests practice (`/practice`)**
    *   The bot checks if a language is selected and diagnostics are completed.
    *   If there's an active practice question, it reminds the user.
    *   It finds the next question from the generated plan and sends it.
    *   If the plan is empty or all questions are completed, it sends an appropriate message.
*   **Step 5: User sends a text answer to a practice question**
    *   The bot receives the answer.
    *   Sends the answer to an LLM for evaluation.
    *   Saves the user's answer and the LLM's feedback.
    *   Sends the LLM feedback to the user along with a "Next question" button.
*   **Step 6: User clicks "Next question"**
    *   The bot finds and sends the next question from the practice plan.
    *   If there are no more questions in the plan, it informs the user that all practice questions have been completed.
