# telegram-rest-mvc

Minimal MVC routing helper for **python-telegram-bot v20+**.

```python
from telegram_rest_mvc.router import Router, path

router = Router()

# Register a command
path(router, "/start", StartView.as_handler())
```

## Installation

```bash
pip install telegram-rest-mvc
```

## Features
* Django-like route helpers (`path`, `callback`, `message`).
* Class-based views with convenient access to `self.update` / `self.context`.
* Simple registrar to attach all routes to a PTB `Application`.

## License
MIT
