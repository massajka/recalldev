from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import os
import json
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage

# Инициализация LLM
llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0, openai_api_key=os.getenv("OPENAI_API_KEY"))

# Файл для хранения прогресса
PROGRESS_FILE = "user_progress.json"

def save_user_progress(user_id, data):
    try:
        with open(PROGRESS_FILE, "r") as f:
            all_data = json.load(f)
    except FileNotFoundError:
        all_data = {}
    all_data[str(user_id)] = data
    with open(PROGRESS_FILE, "w") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

def load_user_progress(user_id):
    try:
        with open(PROGRESS_FILE, "r") as f:
            all_data = json.load(f)
        return all_data.get(str(user_id), {})
    except FileNotFoundError:
        return {}

# ТЕМЫ ДЛЯ ДИАГНОСТИКИ
topics = [
    "ООП",
]

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['topic_scores'] = {}
    await update.message.reply_text(
        "Привет! Я помогу тебе освежить знания по Python. Начнём с диагностики. Оцени свою уверенность в теме:"
    )
    await ask_next_topic(update, context)

# Задать следующий вопрос диагностики
async def ask_next_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scores = context.user_data['topic_scores']
    for topic in topics:
        if topic not in scores:
            keyboard = [
                [InlineKeyboardButton(f"{i}", callback_data=f"score|{i}|{topic}") for i in range(6)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Оцени свою уверенность по теме: {topic}", reply_markup=reply_markup)
            return
    await suggest_learning_plan(update, context)

# Обработка выбора оценки
async def handle_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, score, topic = query.data.split("|")
    context.user_data['topic_scores'][topic] = int(score)
    await query.edit_message_text(f"{topic}: {score}/5")
    await ask_next_topic(query, context)

# Предложение плана и генерация вопросов
async def suggest_learning_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scores = context.user_data['topic_scores']
    sorted_scores = sorted(scores.items(), key=lambda x: x[1])
    diagnostics_str = "\n".join([f"{topic}: {score}/5" for topic, score in sorted_scores])

    prompt = f"""
Пользователь прошёл диагностику по темам Python. Его цель — освежить знания, а не изучать с нуля. Он уже опытный разработчик. Вот его самооценки:
{diagnostics_str}

Составь список углублённых, но коротких и атомарных вопросов, каждый из которых проверяет знание одного конкретного аспекта темы. Избегай вопросов, объединяющих сразу несколько тем.

Например, вместо:
- Какие принципы ООП вы знаете и как они применяются в Python?

Разбей на:
- Какие принципы ООП вы знаете?
- Что такое инкапсуляция и как она реализуется в Python?
- Как работает наследование в Python?
- Чем отличается перегрузка от переопределения?

Верни результат в формате JSON:  "Тема": ["вопрос 1", "вопрос 2"] 
"""
    
    response = llm([HumanMessage(content=prompt)])
    questions_by_topic = json.loads(response.content)

    context.user_data['question_plan'] = questions_by_topic
    context.user_data['question_list'] = [(topic, q) for topic, questions in questions_by_topic.items() for q in questions]
    context.user_data['current_q_index'] = 0

    await update.message.reply_text("📊 Обучающий план готов. Готов начать? Напиши /go")

# Команда /go для старта вопросов
async def go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_next_refresh_question(update, context)

# Отправка вопроса
async def send_next_refresh_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q_list = context.user_data.get('question_list', [])
    idx = context.user_data.get('current_q_index', 0)
    if update.message:
        user_id = update.message.from_user.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
    else:
        user_id = None  # или выбросить ошибку

    if idx >= len(q_list):
        await update.message.reply_text("✅ Все вопросы пройдены!")
        return

    topic, question = q_list[idx]
    context.user_data['current_topic'] = topic
    context.user_data['current_question'] = question
    context.user_data['awaiting_answer'] = True

    await update.message.reply_text(f"🧠 {topic}\n{question}\n\nНапиши свой ответ:")

    save_user_progress(user_id, context.user_data)

# Обработка ответа пользователя и вывод кнопок после анализа
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_answer'):
        await update.message.reply_text("Пожалуйста, дождитесь следующего вопроса.")
        return

    context.user_data['awaiting_answer'] = False

    topic = context.user_data.get('current_topic')
    question = context.user_data.get('current_question')
    answer = update.message.text

    prompt = f"Пользователь ответил на вопрос по теме '{topic}':\nВопрос: {question}\nОтвет: {answer}\n\nПроанализируй ответ, укажи, что правильно, что нет, и объясни тему подробно, включая поведение под капотом и best practices."
    response = llm([HumanMessage(content=prompt)])
    explanation = response.content

    context.user_data['last_explanation'] = explanation

    keyboard = [
        [
            InlineKeyboardButton("Обсудить", callback_data="discuss"),
            InlineKeyboardButton("Следующий вопрос", callback_data="next")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(explanation, reply_markup=reply_markup)

# Обработка кнопки "Следующий вопрос"
async def handle_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['current_q_index'] += 1
    await send_next_refresh_question(query, context)

# Обработка кнопки "Обсудить"
async def handle_discuss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    explanation = context.user_data.get('last_explanation', 'Нет доступного объяснения.')
    await query.edit_message_text(f"💬 Давай обсудим подробнее:\n{explanation}")

# Основной запуск
if __name__ == '__main__':
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_score, pattern="^score\\|"))
    app.add_handler(CallbackQueryHandler(handle_next, pattern="^next$"))
    app.add_handler(CallbackQueryHandler(handle_discuss, pattern="^discuss$"))
    app.add_handler(CommandHandler("go", go))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))

    print("Bot is running...")
    app.run_polling()
