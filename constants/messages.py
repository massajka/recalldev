# constants.py

# --- Callback Data Prefixes ---
# Эти префиксы уже были в main.py, но логично их тоже держать здесь или в отдельном файле конфигурации.
# Пока оставим их в main.py, чтобы не ломать текущую логику без необходимости, если они там используются еще где-то кроме хэндлеров.
# Если они используются ТОЛЬКО для регистрации хэндлеров и формирования callback_data, их можно будет перенести сюда позже.

# --- User-facing Messages ---

# start_command
MSG_WELCOME_BACK = "С возвращением! Ваш текущий язык: {active_lang_name}.\nВы можете продолжить с /diagnostics или /practice, или сменить язык с /language."
MSG_GREETING = "Привет! Я ваш AI-помощник для подготовки к техническим интервью.\nПожалуйста, выберите язык программирования, по которому вы хотите подготовиться:"
MSG_NO_ACTIVE_LANGUAGE_START = "Привет! Я ваш AI-помощник для подготовки к техническим интервью.\nПожалуйста, выберите язык программирования, по которому вы хотите подготовиться:"

# technology_command
MSG_NO_AVAILABLE_TECHNOLOGIES = "В данный момент нет доступных технологий для изучения. Пожалуйста, попробуйте позже."
MSG_CHOOSE_TECHNOLOGY = "Выберите язык или технологию для изучения:"

# handle_language_selection
MSG_LANGUAGE_SELECTED = "Отлично! Вы выбрали язык: {selected_language_name}.\nТеперь давайте начнем с небольшой диагностики. Используйте команду /diagnostics."

# diagnostics_command
MSG_START_DIAGNOSTICS = "Начинаем диагностику! Ответьте на несколько вопросов."
MSG_DIAGNOSTIC_SCORE_PARSE_ERROR = "Ошибка: не удалось разобрать ваш ответ. Пожалуйста, выберите оценку с помощью кнопок."
MSG_LANGUAGE_NOT_FOUND = "Ошибка: Язык '{language_slug}' не найден. Пожалуйста, выберите из списка."
MSG_SELECTED_LANGUAGE_NOT_FOUND_RETRY = "Ошибка: Выбранный язык не найден. Пожалуйста, попробуйте снова."

# send_current_diagnostic_question
MSG_CHOOSE_LANGUAGE_FIRST = "Пожалуйста, сначала выберите язык с помощью /language."
MSG_DIAGNOSTIC_QUESTION_PROMPT = "Диагностический вопрос по теме: **{category_name}**\n\n{question_text}\n\nОцените свои знания по этому вопросу от 1 (совсем не знаю) до 5 (отлично знаю):"
MSG_DIAGNOSTICS_COMPLETE = "Диагностика завершена! 🎉\nТеперь вы можете начать практику с помощью команды /practice."
MSG_NO_ACTIVE_DIAGNOSTIC_QUESTION = "Не найден активный диагностический вопрос. Возможно, диагностика уже пройдена или еще не начата."

# diagnostics_command
MSG_NO_DIAGNOSTIC_QUESTIONS_FOR_LANG = "К сожалению, для выбранного языка пока нет диагностических вопросов."

# handle_diagnostic_score
MSG_ERROR_PROCESSING_SCORE = "Произошла ошибка. Попробуйте еще раз."
MSG_ACTIVE_LANGUAGE_NOT_FOUND_ERROR = "Ошибка: не найден активный язык. Пожалуйста, выберите язык через /language."
MSG_QUESTION_NOT_FOUND_OR_OLD = "Ошибка: вопрос не найден или устарел."
MSG_SCORE_SAVED_CONTINUE = "Ваша оценка {score} по вопросу '{question_text_short}' сохранена."
MSG_ALL_DIAGNOSTIC_QUESTIONS_ANSWERED = "Все диагностические вопросы для языка {language_name} пройдены!"
MSG_DIAGNOSTIC_SCORE_CONFIRMATION = "Диагностический вопрос по теме: **{category_name}**\n\n{question_text}\n\nВаша оценка: **{score}/5**"
MSG_DIAGNOSTICS_SCORES_SAVED_COMPLETE = "Диагностика завершена! 🎉\nВаши самооценки сохранены. Теперь вы можете начать практику с помощью команды /practice."

# practice_command
MSG_NO_DIAGNOSTIC_SCORES = "Пожалуйста, сначала пройдите диагностику (/diagnostics) для выбранного языка, чтобы я мог составить для вас подходящий план."
MSG_GENERATING_PRACTICE_PLAN = "Понял вас. Сейчас я проанализирую ваши ответы в диагностике и составлю персональный план практических вопросов. Это может занять некоторое время...⏳"
MSG_PRACTICE_PLAN_GENERATION_FAILED = "Не удалось сгенерировать план практики. Попробуйте позже или обратитесь к администратору."
MSG_NO_QUESTIONS_FOR_PLAN = "Не смог подобрать вопросы для вашего плана практики по языку {language_name}. Возможно, стоит пересмотреть критерии или добавить больше вопросов в базу."
MSG_PRACTICE_PLAN_READY = "Ваш план практики готов! Начнем с первого вопроса."
MSG_ALREADY_IN_DIAGNOSTICS = "Вы находитесь в режиме диагностики. Завершите его или используйте /practice для обычных вопросов."
MSG_NO_ACTIVE_PRACTICE_QUESTION = "Не найден активный практический вопрос. Возможно, стоит сгенерировать новый план /practice или вы завершили текущий."

MSG_PRACTICE_PLAN_FINISHED_INSTRUCTIONS = (
    "Отлично, вы прошли все вопросы в данном практическом плане!\n"
    "Чтобы начать новый по этой технологии введите команду /diagnostics\n"
    "Чтобы изменить технологию введите команду /technology"
)

MSG_PRACTICE_PLAN_FINISHED = "План практики не найден или вопросы закончились. Используйте /start или /diagnostics для начала нового цикла."

# send_current_practice_question
MSG_PRACTICE_QUESTION_INTRO = "Практический вопрос по теме: **{category_name}**\nЯзык: {language_name}"
MSG_PRACTICE_QUESTION_TEXT = "\n{question_text}"
MSG_AWAITING_YOUR_ANSWER = "\n\n📝 Жду вашего ответа..."
MSG_PRACTICE_QUESTION_FULL_PROMPT = "Практический вопрос по теме: **{category_name}**\n\n{question_text}\n\nНапишите свой развернутый ответ:"

# practice_command specific messages
MSG_ACTIVE_QUESTION_CONTINUE = "У вас есть активный вопрос. Давайте продолжим!"
MSG_FOUND_NEXT_QUESTION_IN_PLAN = "Нашел следующий вопрос в вашем плане."
MSG_CREATING_NEW_PRACTICE_PLAN_FROM_DIAGNOSTICS = "Отлично! Сейчас я составлю для вас новый персонализированный план на основе вашей диагностики..."
MSG_DIAGNOSTIC_LOAD_ERROR = "Не удалось загрузить результаты вашей диагностики. Пожалуйста, попробуйте пройти ее снова /diagnostics."
MSG_NEW_PRACTICE_QUESTIONS_READY = "Я подготовил для вас {count} новых вопросов. Начнем!"
MSG_PRACTICE_PLAN_GENERATION_FAILED_NO_QUESTIONS = "Мне не удалось сгенерировать новые вопросы по вашему плану. Возможно, LLM не вернул подходящих вопросов или категории не совпали. Попробуйте позже или обратитесь к администратору."
MSG_PRACTICE_PLAN_GENERATION_ERROR = "Произошла ошибка при генерации вашего учебного плана. Пожалуйста, попробуйте позже."
MSG_UNEXPECTED_ERROR_PRACTICE_PLAN = "Произошла неожиданная ошибка. Пожалуйста, попробуйте позже."

BTN_NEXT_QUESTION = "Следующий вопрос"
# handle_text_message specific messages
MSG_CANT_MATCH_ANSWER_TO_QUESTION = "Произошла ошибка: не могу соотнести ваш ответ с вопросом. Попробуйте /practice."
MSG_THANKS_FOR_ANSWER_ANALYZING = "Спасибо за ответ! Сейчас я его проанализирую... 🤔"
MSG_ACTIVE_LANG_NOT_DEFINED_START_OVER = "Ошибка: не определен активный язык. Пожалуйста, начните с /start."

# Simplified Flow Messages
MSG_PRACTICE_PLAN_READY_USE_PRACTICE = "Ваш персональный план подготовки готов! Чтобы начать, отправьте команду /practice."
MSG_NO_PRACTICE_QUESTIONS_RUN_DIAGNOSTICS = "У вас пока нет вопросов для практики. Диагностика начнется автоматически после выбора языка (команда /language), если вы еще не проходили ее."
MSG_DIAGNOSTICS_AUTO_START_FAIL = "Не удалось автоматически начать диагностику. Попробуйте команду /diagnostics."
MSG_DIAGNOSTICS_STARTING_AUTO = "Начинаем диагностику..."
MSG_DIAGNOSTICS_ALREADY_DONE_PRACTICE_SUGGESTION = "Вы уже проходили диагностику. Ваш персональный план должен быть готов. Попробуйте команду /practice, чтобы начать." # Added this new constant
MSG_LLM_NOT_AVAILABLE_ERROR = "Ошибка: Модель ИИ недоступна. Не могу сгенерировать план."
MSG_PRACTICE_PLAN_GENERATION_ERROR_JSON = "Ошибка при обработке ответа от ИИ (неверный JSON). Не удалось создать план."
MSG_PRACTICE_PLAN_GENERATION_ERROR_FORMAT = "Ошибка при обработке ответа от ИИ (неверный формат данных). Не удалось создать план."
MSG_NO_DIAGNOSTIC_SCORES_RUN_DIAGNOSTICS_FIRST = "Сначала нужно пройти диагностику. Она начнется автоматически после выбора языка (/language)."

# handle_text_message
MSG_LLM_NOT_AVAILABLE = "Вибачте, наразі функція, що потребує мовну модель, недоступна. Спробуйте пізніше."
MSG_LLM_EVALUATION_ERROR = "Произошла ошибка при анализе вашего ответа. Пожалуйста, попробуйте ответить еще раз или пропустить вопрос."
MSG_ANSWER_SAVED_NO_LLM = "Ваш ответ сохранен. (LLM оценка отключена)"
MSG_PROCEED_TO_NEXT_QUESTION = "Ваш ответ сохранен. Нажмите кнопку ниже, чтобы перейти к следующему вопросу."

# handle_next_question_callback
MSG_ALL_QUESTIONS_ANSWERED_CONGRATS = "Поздравляю! Вы ответили на все вопросы в текущем плане. 🎉\nЧтобы сгенерировать новый план, используйте команду /practice."
MSG_ALL_PRACTICE_QUESTIONS_COMPLETED = "Поздравляю! Вы ответили на все вопросы в текущем плане практики. Чтобы сгенерировать новый план по результатам новой диагностики, вы можете снова выбрать язык командой /language."

# General errors / fallback
MSG_GENERAL_ERROR = "Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже."
MSG_COMMAND_NOT_FOUND_START_OVER = "Неизвестная команда или некорректный ввод. Пожалуйста, начните с /start."

